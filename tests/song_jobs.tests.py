"""CPU-only regression checks for job parsing and backend translation."""
import contextlib
import json
import os
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from song_jobs import read_job, read_yaml
from yue import prepare
import yaml


@contextlib.contextmanager
def directory(path):
    original = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


class Jobs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="song job tests ")
        self.root = Path(self.temp.name)
        self.job = self.root / "song.md"
        self.job.write_text("---\ntool: yue\nseed: 7\ntool_options:\n  planning: off\n---\n# A Song\n\nGentle pop\n\n```song-lyrics\n[verse]\nHello sun\n```\n", encoding="utf-8")
        for name in ["python.exe", "backend.py", "acoustic", "ar", "tokenizer", "vae", "vae_config"]:
            (self.root / name).write_text("fixture")
        self.config = dict(version=1, tool="yue", backend="wan2gp-yue2",
            paths=dict(application=".", python="python.exe", entrypoint="backend.py",
                       models={k: k for k in ["acoustic", "ar", "tokenizer", "vae", "vae_config"]}),
            runtime=dict(profile=4, vae_tile_size=256, timeout_seconds=30),
            defaults=dict(seed=1, steps=12, tool_options=dict(planning="full")), output=dict(directory="generated"))
        self.write_config()

    def write_config(self):
        (self.root / "yue.yaml").write_text(yaml.safe_dump(self.config), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_translation_and_precedence(self):
        with directory(self.root):
            request, python, entrypoint, output = prepare(self.job)
        self.assertEqual(request["settings"]["seed"], 7)
        self.assertEqual(request["settings"]["steps"], 12)
        self.assertEqual(request["settings"]["temperature"], 1)
        self.assertEqual(request["settings"]["tool_options"]["planning"], "off")
        self.assertEqual(request["style"], "Gentle pop")
        self.assertEqual(request["lyrics"], "[verse]\nHello sun")
        self.assertEqual(request["config"], str(self.root / "yue.yaml"))
        self.assertEqual(output, self.root / "generated")
        self.assertFalse(output.exists())

    def test_invalid_current_config_does_not_fall_back(self):
        (self.root / "yue.yaml").write_text("[invalid]")
        with directory(self.root), self.assertRaises(ValueError):
            prepare(self.job)

    def test_lookup_falls_back_beside_runner(self):
        invocation = self.root / "invocation"
        invocation.mkdir()
        with directory(invocation), patch("yue.__file__", str(self.root / "yue.py")):
            request, *_ = prepare(self.job)
        self.assertEqual(request["config"], str(self.root / "yue.yaml"))
        self.assertEqual(request["models"]["ar"], str(self.root / "ar"))

    def test_boolean_spellings(self):
        self.assertEqual(read_yaml("planning: off\nflag: false"), {"planning": "off", "flag": False})

    def test_duplicate_and_unsafe_yaml(self):
        for text in ["seed: 1\nseed: 2", "!!python/object/apply:os.system ['echo forbidden']", "<<: {}"]:
            with self.assertRaises((ValueError, yaml.YAMLError)):
                read_yaml(text)

    def test_malformed_jobs(self):
        for text in ["# One\n# Two", "# Song\n```song-lyrics\nunclosed", "# Song\n```python\nprint(1)\n```", "# Song\n```song-lyrics\na\n```\n```song-lyrics\nb\n```", "Prompt before\n# Song"]:
            self.job.write_text(text)
            with self.assertRaises(ValueError):
                read_job(self.job)

    def test_reject_unsupported_and_bad_settings(self):
        for change in [dict(top_p=2), dict(seed=True), dict(unknown=1), dict(tool_options=dict(planning="invalid"))]:
            self.config["defaults"] = change
            self.write_config()
            with directory(self.root), self.assertRaises(ValueError):
                prepare(self.job)
        self.config["defaults"] = {}
        self.write_config()
        self.job.write_text(self.job.read_text() + "\n```song-negative-prompt\nnoise\n```\n")
        with directory(self.root), self.assertRaises(ValueError):
            prepare(self.job)

    def test_style_is_literal_not_executed(self):
        self.job.write_text(self.job.read_text() + "\n```song-positive-style\n$(echo hello); literal\n```\n")
        with directory(self.root):
            request, *_ = prepare(self.job)
        self.assertEqual(request["style"], "$(echo hello); literal")

    def test_generation_preserves_unique_outputs_and_logs(self):
        self.config["paths"]["python"] = sys.executable
        self.write_config()
        (self.root / "backend.py").write_text("import json,sys,wave\nfrom pathlib import Path\nr=json.loads(Path(sys.argv[2]).read_text())\np=Path(r['output'])\nwith wave.open(str(p/'audio.wav'),'wb') as w:\n w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000); w.writeframes(bytes(1920))\nprint('backend fixture')\n")
        runner = Path(__file__).resolve().parents[1] / "bin/yue.py"
        for _ in range(2):
            result = subprocess.run([sys.executable, str(runner), str(self.job)], cwd=self.root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        outputs = list((self.root / "generated").iterdir())
        self.assertEqual(len(outputs), 2)
        for output in outputs:
            self.assertEqual((output / "job.md").read_bytes(), self.job.read_bytes())
            self.assertIn("backend fixture", (output / "stdout.log").read_text())
            self.assertEqual(json.loads((output / "request.json").read_text())["settings"]["seed"], 7)

    def test_backend_failure_is_actionable_and_preserved(self):
        self.config["paths"]["python"] = sys.executable
        self.write_config()
        (self.root / "backend.py").write_text("import sys\nprint('fixture failure',file=sys.stderr)\nsys.exit(4)\n")
        runner = Path(__file__).resolve().parents[1] / "bin/yue.py"
        result = subprocess.run([sys.executable, str(runner), str(self.job)], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("exit 4", result.stderr)
        output = next((self.root / "generated").iterdir())
        self.assertIn("fixture failure", (output / "stderr.log").read_text())
        self.assertTrue((output / "job.md").exists())


if __name__ == "__main__":
    unittest.main()
