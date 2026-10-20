from dataclasses import replace
from pathlib import Path

import pytest

from tool_service.adapters import MusicAdapter
from tool_service.app import create_app
from tool_service.config import Settings


class FakeAdapter(MusicAdapter):
    def __init__(self, settings):
        self.name = "ace-step"
        self.settings = settings
        self.runner = Path(__file__).with_name("fake_runner.py")
        self.cwd = settings.repository
        self.example = "# Example\n\nA test song"
        self.description = "Generate a test WAV without a GPU"
        self.ready = True

    def timeout(self):
        return 10

    async def available(self):
        return self.ready


@pytest.fixture
def settings(tmp_path):
    return Settings(tmp_path, tmp_path, tmp_path / "jobs", tmp_path / "keys.yaml",
                    "127.0.0.1", 8000, "http://testserver", ["testserver", "127.0.0.1", "localhost"],
                    ["http://testserver", "http://127.0.0.1:8000"], ["ace-step"])


@pytest.fixture
def adapter(settings):
    return FakeAdapter(settings)


@pytest.fixture
def app(settings, adapter):
    return create_app(settings, {"ace-step": adapter}, ["alice:password", "bob-key"])
