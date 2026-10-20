import asyncio
from pathlib import Path
import sys
import tempfile

import soundfile as sf

from .config import read_yaml
from .process import run_python


class ServiceError(Exception):
    def __init__(self, status, code, message, job_id=None):
        super().__init__(message)
        self.status = status
        self.payload = {"code": code, "message": message}
        if job_id:
            self.payload["job_id"] = job_id


class MusicAdapter:
    def __init__(self, name, settings):
        self.name = name
        self.settings = settings
        self.runner = settings.repository / "bin" / f"{name}.py"
        self.cwd = settings.bin_dir
        self.example = (settings.repository / "examples/song-jobs" / f"{name}-first-song.md").read_text(encoding="utf-8")
        self.description = f"Generate a WAV with {name} from a Markdown song job. Submit, then poll get_job."
        self._probe_lock = asyncio.Lock()

    def timeout(self):
        config = read_yaml(self.cwd / f"{self.name}.yaml")
        timeout = config["runtime"]["timeout_seconds"]
        if type(timeout) is not int or not 1 <= timeout <= 86400:
            raise ValueError("Invalid runner timeout")
        return timeout

    async def validate(self, text, directory):
        job = directory / "job.md"
        job.write_text(text, encoding="utf-8")
        try:
            code = await run_python(sys.executable, self.runner, [job, "--validate"],
                                    self.cwd, directory / "validation.log", 60)
        except (OSError, TimeoutError):
            raise ServiceError(503, "tool_unavailable", f"Cannot validate {self.name}; run just validate {self.name}.") from None
        if code:
            raise ServiceError(422, "invalid_input", f"{self.name} rejected this song. Check the tool's Markdown example and supported fields; validation details are retained locally.")

    async def available(self):
        # Probe actual runner validation, including configured model paths and revisions.
        async with self._probe_lock:
            try:
                self.timeout()
                with tempfile.TemporaryDirectory(prefix="tool-probe-") as temp:
                    await self.validate(self.example, Path(temp))
                return True
            except (ServiceError, ValueError, KeyError, TypeError, OSError):
                return False

    async def execute(self, directory):
        output = directory / "output"
        output.mkdir(exist_ok=True)
        code = await run_python(sys.executable, self.runner,
                                [directory / "job.md", "--output-dir", output], self.cwd,
                                directory / "runner.log", self.timeout())
        if code:
            raise ServiceError(500, "runner_failed", f"{self.name} failed (exit {code}); inspect the job's local logs and run just validate {self.name}.")
        candidates = list(output.glob("*/audio.wav"))
        if len(candidates) != 1:
            raise ServiceError(500, "invalid_result", "Runner did not produce exactly one WAV result.")
        result = candidates[0].resolve()
        if not result.is_relative_to(directory.resolve()):
            raise ServiceError(500, "invalid_result", "Runner result escapes the job directory.")
        try:
            info = sf.info(result)
            expected_rate = 44100 if self.name == "minimax-music3" else 48000
            if info.format != "WAV" or info.frames < 1 or info.channels != 2 or info.samplerate != expected_rate:
                raise ValueError("Invalid WAV")
        except (RuntimeError, ValueError, OSError):
            raise ServiceError(500, "invalid_result", "Runner produced an unreadable or invalid WAV.") from None
        return result
