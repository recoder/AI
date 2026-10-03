"""CPU-only MiniMax Music 3 job and WAV validation tests."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import soundfile as sf


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
spec = importlib.util.spec_from_file_location("minimax_music3_runner", ROOT / "bin/minimax-music3.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class MiniMaxMusic3Job(unittest.TestCase):
    def test_example_maps_literal_inputs(self):
        request, python, backend, output = runner.prepare(ROOT / "examples/song-jobs/minimax-music3-first-song.md")
        self.assertIn("acoustic-pop", request["prompt"])
        self.assertIn("Morning light across the bay", request["lyrics"])
        self.assertEqual(10, request["settings"]["duration_seconds"])
        self.assertEqual(30, request["settings"]["steps"])
        self.assertTrue(Path(python).is_file())
        self.assertTrue(Path(backend).is_file())
        self.assertEqual(ROOT / "work/music/generated", output)

    def test_missing_lyrics_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "cache") as temporary:
            job = Path(temporary) / "no-lyrics.md"
            job.write_text("# Instrumental\n\nWarm jazz guitar.\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "song-lyrics"):
                runner.prepare(job)

    def test_lyric_section_text_on_same_line_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "cache") as temporary:
            job = Path(temporary) / "bad-tags.md"
            job.write_text("# Tags\n\nPop song.\n\n```song-lyrics\n[Verse] Hello\n```\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "own lines"):
                runner.prepare(job)

    def test_negative_prompt_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "cache") as temporary:
            job = Path(temporary) / "negative.md"
            job.write_text("# Invalid\n\nPop.\n\n```song-negative-prompt\nnoise\n```\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not support"):
                runner.prepare(job)

    def test_float_wav_is_accepted(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "cache") as temporary:
            path = Path(temporary) / "float.wav"
            sf.write(path, [[0.1, -0.1]] * 441, 44100, subtype="FLOAT")
            self.assertEqual(441, runner.validate_audio(path).frames)

    def test_silent_wav_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "cache") as temporary:
            path = Path(temporary) / "silent.wav"
            sf.write(path, [[0.0, 0.0]] * 441, 44100, subtype="FLOAT")
            with self.assertRaisesRegex(RuntimeError, "silent"):
                runner.validate_audio(path)


if __name__ == "__main__":
    unittest.main()
