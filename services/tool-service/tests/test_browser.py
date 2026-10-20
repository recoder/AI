"""Opt-in real browser check using installed Edge; never downloads a browser."""
from contextlib import contextmanager
from dataclasses import replace
import os
import socket
import threading
import time

import pytest
import uvicorn

from tool_service.app import create_app


@contextmanager
def live_server(app):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets":[sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(.05)
    try:
        assert server.started
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        sock.close()
        assert not thread.is_alive()


@pytest.mark.skipif(os.environ.get("TOOL_SERVICE_BROWSER_TEST") != "1", reason="Set TOOL_SERVICE_BROWSER_TEST=1 to run installed Edge")
def test_ui_submission_download_refresh_and_reauthentication(settings, adapter, tmp_path):
    from playwright.sync_api import sync_playwright, expect
    settings = replace(settings, allowed_origins=[])
    app = create_app(settings, {"ace-step":adapter}, ["browser-test-key"])
    with live_server(app) as base:
        # Settings are immutable; update the underlying list before making requests.
        settings.allowed_origins.append(base)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(accept_downloads=True)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base + "/ui/")
            page.get_by_label("Access key", exact=False).fill("browser-test-key")
            page.get_by_role("button", name="Connect", exact=True).click()
            expect(page.get_by_role("button", name="Download", exact=True)).to_be_enabled()
            with page.expect_download(timeout=20000) as download:
                page.get_by_role("button", name="Download", exact=True).click()
            path = download.value.path()
            assert path.read_bytes().startswith(b"RIFF")
            expect(page.get_by_role("button", name="Download WAV")).to_be_visible()
            page.reload()
            expect(page.get_by_label("Access key", exact=False)).to_have_value("")
            page.get_by_label("Access key", exact=False).fill("browser-test-key")
            page.get_by_role("button", name="Connect", exact=True).click()
            expect(page.get_by_role("button", name="Download WAV")).to_be_visible()
            with page.expect_download():
                page.get_by_role("button", name="Download WAV").click()
            page.get_by_label("Markdown song job").fill("# Slow\n\nSLOW")
            page.get_by_role("button", name="Download", exact=True).click()
            expect(page.get_by_role("status")).to_contain_text("ace-step:")
            page.reload()
            page.get_by_label("Access key", exact=False).fill("browser-test-key")
            page.get_by_role("button", name="Connect", exact=True).click()
            expect(page.get_by_role("button", name="Download WAV")).to_have_count(2, timeout=20000)
            page.screenshot(path=str(tmp_path / "ui.png"), full_page=True)
            assert not errors
            browser.close()
