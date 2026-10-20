from contextlib import contextmanager
from datetime import datetime, timezone
import json
import sqlite3
import sys


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def instance_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "service.lock").open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError("Another tool-service instance is using this state directory") from None
        try:
            yield
        finally:
            handle.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


class Store:
    def __init__(self, directory):
        self.connection = sqlite3.connect(directory / "jobs.sqlite3")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.connection.close()
            raise RuntimeError("Unsupported job database version; preserve it and use the matching service version")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT UNIQUE NOT NULL, owner TEXT NOT NULL, tool TEXT NOT NULL,
                fingerprint TEXT NOT NULL, idempotency_key TEXT,
                state TEXT NOT NULL, created_at TEXT NOT NULL,
                started_at TEXT, finished_at TEXT, result TEXT, error TEXT,
                UNIQUE(owner, idempotency_key)
            );
            CREATE INDEX IF NOT EXISTS jobs_owner ON jobs(owner, sequence);
            CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state, sequence);
            PRAGMA user_version=1;
        """)

    def recover(self):
        with self.connection:
            self.connection.execute(
                "UPDATE jobs SET state='interrupted', finished_at=?, error=? WHERE state='running'",
                (now(), json.dumps({"code": "interrupted", "message": "Service stopped during generation. Partial files were retained; submit a new job to retry."})),
            )

    def duplicate(self, owner, key):
        if key is None:
            return None
        return self.connection.execute("SELECT * FROM jobs WHERE owner=? AND idempotency_key=?", (owner, key)).fetchone()

    def get(self, owner, job_id):
        return self.connection.execute("SELECT * FROM jobs WHERE owner=? AND id=?", (owner, job_id)).fetchone()

    def list(self, owner, limit, offset):
        rows = self.connection.execute("SELECT * FROM jobs WHERE owner=? ORDER BY sequence DESC LIMIT ? OFFSET ?", (owner, limit, offset)).fetchall()
        total = self.connection.execute("SELECT COUNT(*) FROM jobs WHERE owner=?", (owner,)).fetchone()[0]
        return rows, total

    def queued_count(self):
        return self.connection.execute("SELECT COUNT(*) FROM jobs WHERE state='queued'").fetchone()[0]

    def insert(self, job_id, owner, tool, fingerprint, key):
        with self.connection:
            self.connection.execute(
                "INSERT INTO jobs(id,owner,tool,fingerprint,idempotency_key,state,created_at) VALUES(?,?,?,?,?,'queued',?)",
                (job_id, owner, tool, fingerprint, key, now()),
            )

    def claim(self):
        with self.connection:
            row = self.connection.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY sequence LIMIT 1").fetchone()
            if row:
                self.connection.execute("UPDATE jobs SET state='running', started_at=? WHERE id=?", (now(), row["id"]))
            return row

    def finish(self, job_id, state, result=None, error=None):
        with self.connection:
            self.connection.execute("UPDATE jobs SET state=?,finished_at=?,result=?,error=? WHERE id=?",
                                    (state, now(), result, json.dumps(error) if error else None, job_id))

    def close(self):
        self.connection.close()
