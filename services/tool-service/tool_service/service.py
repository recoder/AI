import asyncio
from contextlib import asynccontextmanager, suppress
import hashlib
import json
import logging
import os
import re
import uuid

from .adapters import MusicAdapter, ServiceError
from .store import Store, instance_lock

logger = logging.getLogger("tool_service")


class Service:
    def __init__(self, settings, adapters=None):
        self.settings = settings
        self.adapters = adapters if adapters is not None else {name: MusicAdapter(name, settings) for name in settings.tools}
        self.submission_lock = asyncio.Lock()
        self.wake = asyncio.Event()
        self.store = None
        self.worker_task = None

    @asynccontextmanager
    async def lifespan(self):
        with instance_lock(self.settings.state_dir):
            self.store = Store(self.settings.state_dir)
            try:
                self.store.recover()
                self.worker_task = asyncio.create_task(self.worker())
                yield
            finally:
                if self.worker_task:
                    self.worker_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await self.worker_task
                self.store.close()

    def public(self, row):
        result = {name: row[name] for name in ("id", "tool", "state", "created_at", "started_at", "finished_at")}
        base = f"{self.settings.public_url}/api/jobs/{row['id']}"
        result.update(status_url=base, download_url=base + "/download" if row["state"] == "succeeded" else None,
                      error=json.loads(row["error"]) if row["error"] else None)
        return result

    def get(self, owner, job_id):
        if not isinstance(job_id, str) or not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise ServiceError(404, "not_found", "Job not found.")
        row = self.store.get(owner, job_id)
        if row is None:
            raise ServiceError(404, "not_found", "Job not found.")
        return row

    def list(self, owner, limit=20, offset=0):
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 9223372036854775807:
            raise ServiceError(422, "invalid_pagination", "limit must be 1–100 and offset must be nonnegative.")
        rows, total = self.store.list(owner, limit, offset)
        return {"jobs": [self.public(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    async def tools(self):
        result = []
        for name, adapter in self.adapters.items():
            available = await adapter.available()
            result.append({"name": name, "description": adapter.description, "available": available,
                           "example": adapter.example, "repair": None if available else f"just validate {name}"})
        return result

    async def submit(self, owner, name, text, key=None):
        if name not in self.adapters:
            raise ServiceError(404, "unknown_tool", "Unknown tool.")
        if not isinstance(text, str) or not text.strip():
            raise ServiceError(422, "invalid_input", "text must be a nonempty Markdown string.")
        try:
            encoded = text.encode("utf-8")
        except UnicodeEncodeError:
            raise ServiceError(422, "invalid_input", "text must contain valid Unicode.") from None
        if len(encoded) > self.settings.max_text_bytes:
            raise ServiceError(413, "input_too_large", "Submitted text exceeds the configured byte limit.")
        if key is not None and (not isinstance(key, str) or not re.fullmatch(r"[\x21-\x7e]{1,200}", key)):
            raise ServiceError(422, "invalid_idempotency_key", "Idempotency key must be 1–200 printable ASCII characters without spaces.")
        fingerprint = hashlib.sha256(name.encode() + b"\0" + encoded).hexdigest()
        async with self.submission_lock:
            row = self.store.duplicate(owner, key)
            if row:
                if row["fingerprint"] != fingerprint:
                    raise ServiceError(409, "idempotency_conflict", "This idempotency key was already used for different input.")
                return self.public(row)
            if self.worker_task.done():
                raise ServiceError(503, "worker_unavailable", "Generation worker stopped; restart the service and inspect local logs.")
            if self.store.queued_count() >= self.settings.max_queued:
                raise ServiceError(429, "queue_full", "The generation queue is full; retry later.")
            adapter = self.adapters[name]
            if not await adapter.available():
                raise ServiceError(503, "tool_unavailable", f"{name} is unavailable; run just validate {name}.")
            job_id = uuid.uuid4().hex
            directory = self.settings.state_dir / job_id
            directory.mkdir()
            # Retain rejected input and validation diagnostics for the local operator too.
            await adapter.validate(text, directory)
            # Commit the input file before acknowledging its durable database row.
            with (directory / "job.md").open("wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            self.store.insert(job_id, owner, name, fingerprint, key)
            self.wake.set()
            return self.public(self.store.get(owner, job_id))

    async def worker(self):
        while True:
            self.wake.clear()
            row = self.store.claim()
            if row is None:
                await self.wake.wait()
                continue
            job_id = row["id"]
            directory = self.settings.state_dir / job_id
            logger.info("Job %s started (%s)", job_id, row["tool"])
            try:
                adapter = self.adapters.get(row["tool"])
                if adapter is None:
                    raise ServiceError(503, "tool_disabled", "The job's tool is no longer enabled.")
                result = await adapter.execute(directory)
                result = result.resolve()
                if not result.is_relative_to(directory.resolve()) or not result.is_file():
                    raise ServiceError(500, "invalid_result", "No valid job result is available.")
                self.store.finish(job_id, "succeeded", str(result.relative_to(directory.resolve())))
                logger.info("Job %s succeeded", job_id)
            except asyncio.CancelledError:
                self.store.finish(job_id, "interrupted", error={"code": "interrupted", "message": "Service stopped during generation; submit a new job to retry."})
                raise
            except TimeoutError:
                logger.warning("Job %s timed out", job_id)
                self.store.finish(job_id, "failed", error={"code": "timeout", "message": "Generation exceeded its configured time limit. Partial files were retained."})
            except ServiceError as error:
                logger.warning("Job %s failed: %s", job_id, error.payload["code"])
                self.store.finish(job_id, "failed", error=error.payload)
            except Exception:
                # Raw exception details may contain paths/input; keep them in operator logs only.
                logger.exception("Job %s failed", job_id)
                self.store.finish(job_id, "failed", error={"code": "execution_failed", "message": "Generation failed; ask the operator to inspect local logs for this job."})

    def download(self, owner, job_id):
        row = self.get(owner, job_id)
        if row["state"] != "succeeded":
            raise ServiceError(409, "result_not_ready", "Job has not completed successfully.", job_id)
        directory = (self.settings.state_dir / row["id"]).resolve()
        path = (directory / row["result"]).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise ServiceError(410, "result_missing", "The result is no longer available.", job_id)
        return path
