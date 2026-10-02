"""CPU-only ACE-Step job/config translation tests."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import soundfile as sf


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
spec = importlib.util.spec_from_file_location("ace_step_runner", ROOT / "bin/ace-step.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class AceStepJob(unittest.TestCase):
    def test_tracked_example_maps_literal_inputs(self):
        request, python, backend, output = runner.prepare(ROOT / "examples/song-jobs/ace-step-first-song.md")
        self.assertEqual("acestep-v15-xl-sft", request["runtime"]["dit_model"])
        self.assertIn("polished synth-pop", request["caption"])
        self.assertIn("Streetlights bloom", request["lyrics"])
        self.assertFalse(request["settings"]["tool_options"]["instrumental"])
        self.assertEqual(50, request["settings"]["steps"])
        self.assertTrue(Path(python).is_file())
        self.assertTrue(Path(backend).is_file())
        self.assertEqual(ROOT / "work/music/generated", output)
    def test_explicit_declared_fallback_is_allowed(self):
        original = runner.read_yaml
        def fallback_config(text):
            config = original(text)
            config["runtime"]["dit_model"] = config["runtime"]["fallback_dit_model"]
            return config
        runner.read_yaml = fallback_config
        try:
            request, *_ = runner.prepare(ROOT / "examples/song-jobs/ace-step-first-song.md")
            self.assertEqual("acestep-v15-turbo", request["runtime"]["dit_model"])
        finally:
            runner.read_yaml = original


    def test_instrumental_is_inferred_without_lyrics(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "cache") as temporary:
            job = Path(temporary) / "instrumental.md"
            job.write_text("# Instrumental\n\nDetailed ambient jazz with acoustic bass.\n", encoding="utf-8")
            request, *_ = runner.prepare(job)
            self.assertTrue(request["settings"]["tool_options"]["instrumental"])
            self.assertEqual("", request["lyrics"])

    def test_negative_prompt_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "cache") as temporary:
            job = Path(temporary) / "negative.md"
            job.write_text(
                "# Invalid\n\nRock song.\n\n```song-negative-prompt\nnoise\n```\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "does not support"):
                runner.prepare(job)

    def test_float_wav_is_accepted(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "cache") as temporary:
            path = Path(temporary) / "float.wav"
            sf.write(path, [[0.1, -0.1]] * 480, 48000, subtype="FLOAT")
            self.assertEqual(480, runner.validate_audio(path).frames)

    def test_invalid_quality_controls_are_rejected(self):
        settings = runner.DEFAULTS.copy()
        settings["tool_options"] = runner.DEFAULTS["tool_options"].copy()
        settings["steps"] = 0
        with self.assertRaisesRegex(ValueError, "steps"):
            runner.validate_settings(settings)


if __name__ == "__main__":
    unittest.main()
