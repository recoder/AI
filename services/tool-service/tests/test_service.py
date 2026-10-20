import asyncio
import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import time

import pytest
from starlette.testclient import TestClient

from tool_service.app import create_app
from tool_service.config import load_keys, load_settings
from tool_service.store import Store, instance_lock

AUTH = {"Authorization": "Bearer alice:password"}
BOB = {"Authorization": "Bearer bob-key"}
TEXT = "# First song\n\nA bright test song"


def submit(client, text=TEXT, key=None, headers=AUTH):
    headers = dict(headers)
    if key:
        headers["Idempotency-Key"] = key
    return client.post("/api/tools/ace-step", json={"text": text}, headers=headers)


def wait_job(client, job_id, states=("succeeded", "failed", "interrupted")):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}", headers=AUTH)
        assert response.status_code == 200
        job = response.json()
        if job["state"] in states:
            return job
        time.sleep(.05)
    raise AssertionError("Job did not reach the expected state")


def rpc(client, method, params=None, headers=AUTH, request_id=1):
    body = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        body["params"] = params
    return client.post("/mcp", json=body, headers={**headers, "Accept": "application/json, text/event-stream"})


def test_rest_download_auth_ownership_and_ranges(app):
    with TestClient(app) as client:
        assert client.get("/ui/").status_code == 200
        assert client.get("/api/tools").status_code == 401
        assert client.get("/api/tools", headers={"Authorization": "Basic !!!"}).status_code == 401
        assert client.get("/api/health", headers=AUTH).json()["ready"]
        catalog = client.get("/api/tools", headers=AUTH).json()["tools"]
        assert catalog[0]["available"] and catalog[0]["example"]
        response = submit(client)
        assert response.status_code == 202
        job_id = response.json()["id"]
        assert response.headers["location"].endswith(job_id)
        job = wait_job(client, job_id)
        assert job["state"] == "succeeded"
        basic = {"Authorization": "Basic " + base64.b64encode(b"alice:password").decode()}
        assert client.get(f"/api/jobs/{job_id}", headers=basic).status_code == 200
        assert client.get(f"/api/jobs/{job_id}", headers=BOB).status_code == 404
        assert client.get(f"/api/jobs/{job_id}/download", headers=BOB).status_code == 404
        assert client.get("/api/jobs", headers=BOB).json()["jobs"] == []
        response = client.get(job["download_url"], headers=AUTH)
        assert response.status_code == 200 and response.content.startswith(b"RIFF")
        assert "attachment" in response.headers["content-disposition"]
        part = client.get(job["download_url"], headers={**AUTH, "Range": "bytes=0-3"})
        assert part.status_code == 206 and part.content == b"RIFF"
        assert "owner" not in job and str(app.state.service.settings.state_dir) not in json.dumps(job)


def test_idempotency_pagination_and_validation(app):
    with TestClient(app) as client:
        first = submit(client, key="request-one").json()
        assert submit(client, key="request-one").json()["id"] == first["id"]
        assert submit(client, text=TEXT+" changed", key="request-one").status_code == 409
        assert submit(client, key="request-one", headers=BOB).status_code == 202
        assert client.get("/api/jobs?limit=1", headers=AUTH).json()["total"] == 1
        assert client.get("/api/jobs?limit=0", headers=AUTH).status_code == 422
        assert client.get("/api/jobs?offset=-1", headers=AUTH).status_code == 422
        assert client.get("/api/jobs?offset=99999999999999999999", headers=AUTH).status_code == 422
        assert client.get("/api/jobs?limit=oops", headers=AUTH).status_code == 422
        assert submit(client, text="INVALID").status_code == 422
        assert submit(client, text=" ").status_code == 422
        assert submit(client, text=42).status_code == 422
        assert client.post("/api/tools/ace-step", content=b'{"text":"\\ud800"}', headers={**AUTH,"Content-Type":"application/json"}).status_code == 422
        assert submit(client, text="a" * (1048576+1)).status_code == 413
        assert client.post("/api/tools/ace-step", json={"text": TEXT, "path": "C:/secret"}, headers=AUTH).status_code == 422
        assert client.post("/api/tools/ace-step", content="{", headers={**AUTH,"Content-Type":"application/json"}).status_code == 422
        assert client.post("/api/tools/ace-step", content="text", headers=AUTH).status_code == 415
        assert client.post("/api/tools/unknown", json={"text":TEXT}, headers=AUTH).status_code == 404
        assert client.get("/api/jobs/not-a-job", headers=AUTH).status_code == 404
        assert client.get("/api/jobs/..%5Csecret/download", headers=AUTH).status_code == 404


def test_hosts_origins_and_body_limit(app):
    with TestClient(app) as client:
        assert client.get("/api/tools", headers={**AUTH, "Host":"evil.example"}).status_code == 400
        assert client.get("/api/tools", headers={**AUTH, "Origin":"https://evil.example"}).status_code == 403
        assert client.get("/api/tools", headers={**AUTH, "Origin":"http://testserver"}).status_code == 200
        assert client.options("/api/tools", headers=AUTH).status_code == 405
        response = client.post("/api/tools/ace-step", content=b"x" * (7*1048576), headers=AUTH)
        assert response.status_code == 413
        assert client.post("/mcp", json={}).status_code == 401


def test_queue_serial_capacity_and_unavailable(settings, adapter):
    app = create_app(replace(settings, max_queued=1), {"ace-step":adapter}, ["alice:password"])
    with TestClient(app) as client:
        first = submit(client, text=TEXT+" SLOW").json()
        wait_job(client, first["id"], ("running",))
        second = submit(client, key="second").json()
        assert second["state"] == "queued"
        assert submit(client).status_code == 429
        assert submit(client, key="second").json()["id"] == second["id"]
        first_done = wait_job(client, first["id"])
        second_done = wait_job(client, second["id"])
        assert second_done["started_at"] >= first_done["finished_at"]
        adapter.ready = False
        assert submit(client).status_code == 503


@pytest.mark.parametrize("mode,code", [("FAIL","runner_failed"),("MISSING","invalid_result"),("CORRUPT","invalid_result")])
def test_failure_results(app, mode, code):
    with TestClient(app) as client:
        job = wait_job(client, submit(client, text=TEXT+" "+mode).json()["id"])
        assert job["state"] == "failed" and job["error"]["code"] == code
        assert client.get(f"/api/jobs/{job['id']}/download", headers=AUTH).status_code == 409


def test_shutdown_preserves_queue_and_requires_explicit_retry(settings, adapter):
    app = create_app(settings, {"ace-step":adapter}, ["alice:password"])
    with TestClient(app) as client:
        first = submit(client, text=TEXT+" SLOW", key="original").json()
        wait_job(client, first["id"], ("running",))
        second = submit(client).json()
    app = create_app(settings, {"ace-step":adapter}, ["alice:password"])
    with TestClient(app) as client:
        assert client.get(first["status_url"], headers=AUTH).json()["state"] == "interrupted"
        assert wait_job(client, second["id"])["state"] == "succeeded"
        assert submit(client, text=TEXT+" SLOW", key="original").json()["state"] == "interrupted"
        assert (settings.state_dir / first["id"] / "job.md").exists()


def test_crash_recovery_and_single_instance(settings):
    with instance_lock(settings.state_dir):
        with pytest.raises(RuntimeError):
            with instance_lock(settings.state_dir):
                pass
        store = Store(settings.state_dir)
        owner = hashlib.sha256(b"alice:password").hexdigest()
        store.insert("a"*32, owner, "ace-step", "x", None)
        store.claim()
        store.close()
    store = Store(settings.state_dir)
    store.recover()
    assert store.get(owner, "a"*32)["state"] == "interrupted"
    store.close()


def test_mcp_and_rest_share_jobs_and_ownership(app):
    with TestClient(app) as client:
        init = rpc(client, "initialize", {"protocolVersion":"2025-03-26", "capabilities":{}, "clientInfo":{"name":"test","version":"1"}})
        assert init.status_code == 200, init.text
        names = {tool["name"] for tool in rpc(client,"tools/list").json()["result"]["tools"]}
        assert names == {"ace-step", "get_job", "list_jobs"}
        response = rpc(client, "tools/call", {"name":"ace-step", "arguments":{"text":TEXT,"idempotency_key":"mcp-one"}})
        result = response.json()["result"]
        assert not result.get("isError"), result
        job_id = result["structuredContent"]["id"]
        assert submit(client, key="mcp-one").json()["id"] == job_id
        assert wait_job(client, job_id)["state"] == "succeeded"
        result = rpc(client,"tools/call",{"name":"get_job","arguments":{"job_id":job_id}}).json()["result"]
        assert result["structuredContent"]["download_url"]
        other = rpc(client,"tools/call",{"name":"get_job","arguments":{"job_id":job_id}},headers=BOB).json()["result"]
        assert other["isError"] and other["structuredContent"]["code"] == "not_found"
        jobs = rpc(client,"tools/call",{"name":"list_jobs","arguments":{}}).json()["result"]
        assert jobs["structuredContent"]["total"] == 1


def test_keys_reject_invalid_and_do_not_echo_secrets(tmp_path):
    path = tmp_path / "keys.yaml"
    for text in ("[]", "- abc\n- abc", "- ''", "- replace-with-a-long-random-key", "- [secret-token"):
        path.write_text(text)
        with pytest.raises(ValueError) as error:
            load_keys(path)
        assert "secret-token" not in str(error.value)
    path.write_text("- user:password\n- opaque")
    assert load_keys(path) == ["user:password", "opaque"]


def test_unexpected_errors_do_not_expose_paths_over_rest_or_mcp(app, monkeypatch):
    async def broken(*args, **kwargs):
        raise OSError("Cannot write C:/private/operator/config.yaml")
    monkeypatch.setattr(app.state.service, "submit", broken)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = submit(client)
        assert response.status_code == 500
        assert response.json()["code"] == "internal_error"
        assert "C:/private" not in response.text
        response = rpc(client, "tools/call", {"name":"ace-step","arguments":{"text":TEXT}})
        result = response.json()["result"]
        assert result["isError"] and result["structuredContent"]["code"] == "internal_error"
        assert "C:/private" not in response.text


def test_workspace_override(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_WORKSPACE_ROOT", str(tmp_path))
    settings = load_settings()
    assert settings.bin_dir == tmp_path / "bin"
    assert settings.state_dir == tmp_path / "work/tool-service/jobs"
