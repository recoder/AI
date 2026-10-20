import argparse
import asyncio
import json
import logging
from logging.handlers import RotatingFileHandler
import sqlite3
import sys
from urllib.error import URLError
from urllib.request import Request

from .adapters import MusicAdapter
from .app import create_app
from .config import load_keys, load_settings


async def diagnose(settings, deep):
    failures = 0
    print("  OK tool-service configuration and Python dependencies")
    try:
        keys = load_keys(settings.keys_file)
        print("  OK access keys configured (values hidden)")
    except ValueError:
        keys = []
        failures += 1
        print("  FAIL access keys: create config/tool-service.keys.yaml from its example and replace the examples")
    database = settings.state_dir / "jobs.sqlite3"
    if database.exists():
        try:
            connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
            try:
                if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ValueError("Database check failed")
                if connection.execute("PRAGMA user_version").fetchone()[0] != 1:
                    raise ValueError("Database version mismatch")
                counts = dict(connection.execute("SELECT state,COUNT(*) FROM jobs GROUP BY state"))
                print("  OK job database: " + json.dumps(counts))
            finally:
                connection.close()
        except (sqlite3.Error, ValueError):
            failures += 1
            print("  FAIL job database: preserve the database and inspect service logs before repair")
    else:
        print("  INFO job database will be initialized by just serve")
    if deep:
        for name in settings.tools:
            if await MusicAdapter(name, settings).available():
                print(f"  OK adapter {name}: runner validation passed without generation")
            else:
                failures += 1
                print(f"  FAIL adapter {name}: run just validate {name}")
    else:
        print("  INFO enabled adapters: " + ", ".join(settings.tools))
    if keys:
        # Probe the listener itself, not an administrator-supplied public URL that
        # might forward credentials outside this machine. Never follow redirects.
        from urllib.request import HTTPRedirectHandler, build_opener
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        host = "127.0.0.1" if settings.host == "0.0.0.0" else settings.host
        request = Request(f"http://{host}:{settings.port}/api/health", headers={"Authorization": "Bearer " + keys[0]})
        try:
            with build_opener(NoRedirect).open(request, timeout=3) as response:
                result = json.load(response)
            if result != {"service": "local-tool-service", "ready": True}:
                raise ValueError("Unexpected health response")
            print("  OK running service health")
        except (URLError, OSError, ValueError):
            print("  INFO service is not healthy/listening; start with just serve (foreground)")
    return failures


def main():
    parser = argparse.ArgumentParser(description="Local REST, UI and MCP tool service")
    parser.add_argument("--config")
    parser.add_argument("--check", action="store_true", help="Inspect configured state without creating jobs")
    parser.add_argument("--deep", action="store_true", help="Also validate each runner without generation")
    args = parser.parse_args()
    try:
        settings = load_settings(args.config)
        if args.check:
            raise SystemExit(1 if asyncio.run(diagnose(settings, args.deep)) else 0)
        keys = load_keys(settings.keys_file)
        settings.state_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(settings.state_dir / "service.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        import uvicorn
        uvicorn.run(create_app(settings, keys=keys), host=settings.host, port=settings.port,
                    workers=1, proxy_headers=False, access_log=False, timeout_graceful_shutdown=10)
    except (ValueError, OSError, KeyError, TypeError):
        # Configuration errors can contain secret material; do not echo parser internals.
        print("Tool service cannot start: check config/tool-service.yaml, workspace paths, and the local keys file. Run just validate tool-service.", file=sys.stderr)
        raise SystemExit(1) from None
