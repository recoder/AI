"""Offline runner fixture with the production CLI contract."""
import argparse
from pathlib import Path
import time
import wave

parser = argparse.ArgumentParser()
parser.add_argument("job", type=Path)
parser.add_argument("--validate", action="store_true")
parser.add_argument("--output-dir", type=Path)
args = parser.parse_args()
text = args.job.read_text(encoding="utf-8")
if not text.startswith("# ") or "INVALID" in text:
    raise SystemExit(1)
if args.validate:
    raise SystemExit(0)
if "SLOW" in text:
    time.sleep(2)
if "FAIL" in text:
    raise SystemExit(7)
output = args.output_dir / "fake-run"
output.mkdir(parents=True)
if "MISSING" in text:
    raise SystemExit(0)
if "CORRUPT" in text:
    (output / "audio.wav").write_text("not audio")
    raise SystemExit(0)
with wave.open(str(output / "audio.wav"), "wb") as audio:
    audio.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
    audio.writeframes(b"\x01\x00\x01\x00" * 240)
