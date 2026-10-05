"""CPU-only security-version guard tests for the YuE runtime."""
import importlib.util
from pathlib import Path
import unittest


BACKEND = Path(__file__).resolve().parents[1] / "bin/yue_backend.py"
spec = importlib.util.spec_from_file_location("yue_backend", BACKEND)
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


class TransformersVersionGuard(unittest.TestCase):
    def test_vulnerable_pin_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "security floor"):
            backend.require_secure_transformers_version("4.54.0")

    def test_reviewed_pin_is_allowed(self):
        backend.require_secure_transformers_version("5.13.1")


if __name__ == "__main__":
    unittest.main()
