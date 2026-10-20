"""Internal entry point: EOF before release means the supervising parent died."""
import runpy
import sys
from pathlib import Path

if sys.stdin.buffer.read(1) != b"G":
    raise SystemExit(1)
runner = Path(sys.argv[1]).resolve()
sys.argv = sys.argv[1:]
sys.path.insert(0, str(runner.parent))
runpy.run_path(str(runner), run_name="__main__")
