"""Run a Python entry point only after its process tree is supervised."""
import asyncio
import os
from pathlib import Path
import signal
import subprocess
import sys


async def run_python(python, runner, arguments, cwd, log, timeout):
    job = None
    process = None
    with Path(log).open("wb") as output:
        try:
            process = subprocess.Popen(
                [str(python), str(Path(__file__).with_name("gate.py")), str(runner), *map(str, arguments)],
                cwd=cwd, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                start_new_session=sys.platform != "win32",
            )
            if sys.platform == "win32":
                import win32api
                import win32con
                import win32job
                job = win32job.CreateJobObject(None, "")
                limits = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
                limits["BasicLimitInformation"]["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, limits)
                handle = win32api.OpenProcess(win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, process.pid)
                try:
                    win32job.AssignProcessToJobObject(job, handle)
                finally:
                    handle.Close()
            # The child cannot spawn inference descendants until assignment has succeeded.
            process.stdin.write(b"G")
            process.stdin.close()
            async with asyncio.timeout(timeout):
                while process.poll() is None:
                    await asyncio.sleep(0.05)
            return process.returncode
        finally:
            if job is not None:
                job.Close()  # Also removes descendants left behind by a successful parent.
            if process is not None:
                if sys.platform != "win32":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # The entire process group already exited.
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
