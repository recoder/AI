import base64
from contextvars import ContextVar
import hashlib
import hmac
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse

owner_context = ContextVar("tool_service_owner", default=None)


class Security:
    def __init__(self, app, settings, keys):
        self.app = app
        self.settings = settings
        self.key_hashes = [hashlib.sha256(key.encode("utf-8")).digest() for key in keys]

    def authenticate(self, authorization):
        try:
            scheme, credential = authorization.split(" ", 1)
            if scheme.lower() == "basic":
                raw = base64.b64decode(credential, validate=True)
                if b":" not in raw:
                    return None
                credential = raw.decode("utf-8")
            elif scheme.lower() != "bearer":
                return None
            digest = hashlib.sha256(credential.encode("utf-8")).digest()
            matches = [hmac.compare_digest(digest, candidate) for candidate in self.key_hashes]
            return digest.hex() if any(matches) else None
        except (ValueError, UnicodeError):
            return None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)

        async def reject(status, code, message):
            await JSONResponse({"code": code, "message": message}, status_code=status,
                               headers={"Cache-Control": "no-store"})(scope, receive, send)

        try:
            host_url = urlsplit("//" + headers.get("host", ""))
            host = host_url.hostname if not (host_url.username or host_url.password or host_url.path or host_url.query or host_url.fragment) else None
        except ValueError:
            host = None
        if host not in self.settings.allowed_hosts:
            return await reject(400, "invalid_host", "Host is not allowed.")
        if len(headers.getlist("host")) != 1 or len(headers.getlist("origin")) > 1:
            return await reject(400, "invalid_headers", "Supply exactly one Host and at most one Origin header.")
        origin = headers.get("origin")
        if origin and origin not in self.settings.allowed_origins:
            return await reject(403, "invalid_origin", "Origin is not allowed.")
        protected = scope["path"].startswith(("/api/", "/mcp"))
        if len(headers.getlist("authorization")) > 1:
            return await reject(401, "unauthorized", "Supply one authorization header.")
        owner = self.authenticate(headers.get("authorization", "")) if protected else None
        if protected and owner is None:
            return await reject(401, "unauthorized", "A valid Bearer key or Basic credential is required.")
        # No CORS response headers: allowed origins constrain same-origin browser requests
        # and MCP Origin checks; they do not grant arbitrary websites API access.
        if scope["method"] == "OPTIONS":
            return await reject(405, "method_not_allowed", "Cross-origin API requests are disabled.")
        if scope["method"] in ("POST", "PUT", "PATCH"):
            maximum = self.settings.max_text_bytes * 6 + 65536  # JSON Unicode escaping overhead.
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > maximum:
                    return await reject(413, "input_too_large", "Request body is too large.")
                if not message.get("more_body", False):
                    break
            delivered = False
            original_receive = receive

            async def buffered_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await original_receive()

            receive = buffered_receive

        async def secure_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"content-security-policy", b"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"),
                ]
            await send(message)

        scope.setdefault("state", {})["owner"] = owner
        token = owner_context.set(owner)
        try:
            await self.app(scope, receive, secure_send)
        finally:
            owner_context.reset(token)
