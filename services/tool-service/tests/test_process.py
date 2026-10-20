import asyncio
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from tool_service.process import run_python


def alive(pid):
    if sys.platform == "win32":
        import win32api
        import win32event
        try:
            handle = win32api.OpenProcess(0x00100000, False, pid)
        except Exception:
            return False
        try:
            return win32event.WaitForSingleObject(handle, 0) == 258
        finally:
            handle.Close()
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def tree_runner(tmp_path):
    runner = tmp_path / "tree.py"
    runner.write_text("""import subprocess,sys,time
from pathlib import Path
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'])
Path('child.pid').write_text(str(child.pid))
time.sleep(120)
""")
    return runner


def wait_pid(tmp_path):
    deadline = time.monotonic() + 15
    path = tmp_path / "child.pid"
    while time.monotonic() < deadline:
        if path.exists() and path.read_text():
            return int(path.read_text())
        time.sleep(.05)
    raise AssertionError("Descendant did not start")


def assert_dead(pid):
    deadline = time.monotonic() + 5
    while alive(pid) and time.monotonic() < deadline:
        time.sleep(.05)
    assert not alive(pid), "Supervised descendant survived"


def test_timeout_kills_descendants(tmp_path):
    runner = tree_runner(tmp_path)
    with pytest.raises(TimeoutError):
        asyncio.run(run_python(sys.executable, runner, [], tmp_path, tmp_path / "runner.log", 2))
    assert_dead(wait_pid(tmp_path))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object crash guarantee")
def test_parent_crash_kills_descendants(tmp_path):
    runner = tree_runner(tmp_path)
    supervisor = tmp_path / "supervisor.py"
    project = Path(__file__).resolve().parents[1]
    supervisor.write_text(
        "import sys,asyncio\n"
        f"sys.path.insert(0,{str(project)!r})\n"
        "from tool_service.process import run_python\n"
        "from pathlib import Path\n"
        f"asyncio.run(run_python(sys.executable, Path({str(runner)!r}), [], Path({str(tmp_path)!r}), Path({str(tmp_path / 'runner.log')!r}), 120))\n"
    )
    process = subprocess.Popen([sys.executable, str(supervisor)], creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        pid = wait_pid(tmp_path)
        assert alive(pid)
    finally:
        process.kill()
        process.wait(timeout=10)
    assert_dead(pid)
