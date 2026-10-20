from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .adapters import ServiceError
from .config import load_keys, load_settings
from .security import Security, owner_context
from .service import Service


def create_app(settings=None, adapters=None, keys=None):
    settings = settings or load_settings()
    keys = load_keys(settings.keys_file) if keys is None else keys
    if not keys:
        raise ValueError("At least one authentication key is required")
    service = Service(settings, adapters)
    mcp = FastMCP(
        "Local Tool Service", stateless_http=True, json_response=True,
        streamable_http_path="/mcp", max_request_body_size=settings.max_text_bytes * 6 + 65536,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[f"{host}:*" for host in settings.allowed_hosts] + settings.allowed_hosts,
            allowed_origins=settings.allowed_origins,
        ),
        instructions="Submit Markdown to a music tool, then poll get_job. Download completed WAV files over HTTP with the same Authorization header. Generation can take hours.",
    )

    def owner():
        result = owner_context.get()
        if result is None:
            raise ServiceError(401, "unauthorized", "Authentication is required.")
        return result

    def mcp_result(data, error=False):
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(data))],
                              structuredContent=data, isError=error)

    def unexpected_mcp_error():
        # The SDK otherwise turns exception strings (including local paths) into
        # tool results. Keep implementation details in the operator's log.
        logging.getLogger("tool_service").exception("MCP operation failed")
        return mcp_result({"code": "internal_error", "message": "The service could not complete the request; inspect local service logs."}, True)

    def register(name, adapter):
        async def submit(text: str, idempotency_key: str | None = None) -> CallToolResult:
            try:
                return mcp_result(await service.submit(owner(), name, text, idempotency_key))
            except ServiceError as error:
                return mcp_result(error.payload, True)
            except Exception:
                return unexpected_mcp_error()
        mcp.add_tool(submit, name=name, description=adapter.description + "\nExample:\n" + adapter.example)

    for name, adapter in service.adapters.items():
        register(name, adapter)

    @mcp.tool()
    async def list_jobs(limit: int = 20, offset: int = 0) -> CallToolResult:
        """List jobs belonging to the authenticated key, newest first."""
        try:
            return mcp_result(service.list(owner(), limit, offset))
        except ServiceError as error:
            return mcp_result(error.payload, True)
        except Exception:
            return unexpected_mcp_error()

    @mcp.tool()
    async def get_job(job_id: str) -> CallToolResult:
        """Get job state and, when complete, its authenticated WAV download URL."""
        try:
            return mcp_result(service.public(service.get(owner(), job_id)))
        except ServiceError as error:
            return mcp_result(error.payload, True)
        except Exception:
            return unexpected_mcp_error()

    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app):
        async with service.lifespan(), mcp.session_manager.run():
            yield

    async def tools(request):
        return JSONResponse({"tools": await service.tools()})

    async def submit(request):
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            raise ServiceError(415, "invalid_content_type", "Use application/json.")
        try:
            payload = await request.json()
        except (ValueError, UnicodeError):
            raise ServiceError(422, "invalid_json", "Expected a JSON object containing text.") from None
        if not isinstance(payload, dict) or set(payload) != {"text"}:
            raise ServiceError(422, "invalid_input", "Expected exactly one field: text.")
        result = await service.submit(request.state.owner, request.path_params["tool_name"],
                                      payload["text"], request.headers.get("idempotency-key"))
        return JSONResponse(result, status_code=202, headers={"Location": result["status_url"]})

    async def jobs(request):
        try:
            limit, offset = int(request.query_params.get("limit", "20")), int(request.query_params.get("offset", "0"))
        except ValueError:
            raise ServiceError(422, "invalid_pagination", "Pagination values must be integers.") from None
        return JSONResponse(service.list(request.state.owner, limit, offset))

    async def job(request):
        return JSONResponse(service.public(service.get(request.state.owner, request.path_params["job_id"])))

    async def download(request):
        job_id = request.path_params["job_id"]
        path = service.download(request.state.owner, job_id)
        return FileResponse(path, media_type="audio/wav", filename=f"{job_id}.wav")

    async def health(request):
        healthy = service.worker_task is not None and not service.worker_task.done()
        try:
            service.store.connection.execute("SELECT 1")
        except Exception:
            healthy = False
        return JSONResponse({"service": "local-tool-service", "ready": healthy}, status_code=200 if healthy else 503)

    async def service_error(request, error):
        return JSONResponse(error.payload, status_code=error.status)

    async def http_error(request, error):
        return JSONResponse({"code": "not_found" if error.status_code == 404 else "http_error",
                             "message": "Route not found." if error.status_code == 404 else "Request method is not supported."}, status_code=error.status_code)

    async def internal_error(request, error):
        logging.getLogger("tool_service").error("Unhandled request error: %s", type(error).__name__)
        return JSONResponse({"code": "internal_error", "message": "The service could not complete the request; inspect local service logs."}, status_code=500)

    async def root(request):
        return RedirectResponse("/ui/")

    mcp_app.exception_handlers[HTTPException] = http_error
    app = Starlette(routes=[
        Route("/", root), Route("/api/health", health), Route("/api/tools", tools),
        Route("/api/tools/{tool_name}", submit, methods=["POST"]),
        Route("/api/jobs", jobs), Route("/api/jobs/{job_id}", job),
        Route("/api/jobs/{job_id}/download", download),
        Mount("/ui", StaticFiles(directory=Path(__file__).with_name("static"), html=True)),
        Mount("/", mcp_app),
    ], lifespan=lifespan, middleware=[Middleware(Security, settings=settings, keys=keys)],
        exception_handlers={ServiceError: service_error, HTTPException: http_error, Exception: internal_error})
    app.state.service = service
    app.state.mcp = mcp
    return app
