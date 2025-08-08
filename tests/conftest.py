# tests/conftest.py
import sys
import types
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# --------------------------------------------------------------------
# Install a fake `jiment_ai_generator_async` BEFORE the app is imported
# --------------------------------------------------------------------
class _FakeGen:
    def __init__(self):
        self.all_images_src = []
        self.prompts = []
        self.submits = 0
        self.downloaded = []
        self.refreshed = 0
        self.new_downloads = 0
        self.started = False
        self.closed = False

    async def start(self):
        self.started = True

    async def close(self):
        self.closed = True

    async def clean_prompt(self):
        self.prompts.clear()

    async def add_prompt(self, content: str):
        self.prompts.append(content)

    async def click_submit(self):
        self.submits += 1

    async def download_images(self, index: int):
        self.downloaded.append(index)

    async def get_all_available_images(self):
        # pretend we discovered 2 images
        self.refreshed += 1
        self.all_images_src = ["img1", "img2"]
        return self.all_images_src

    async def download_new_images(self):
        # pretend we downloaded 2 new images
        self.new_downloads += 2
        return ["imgA", "imgB"]


_fake_mod = types.ModuleType("jiment_ai_generator_async")
_fake_mod.JimengAIGenerator = _FakeGen
sys.modules["jiment_ai_generator_async"] = _fake_mod


@pytest.fixture(autouse=True)
def clean_output_dirs():
    """Ensure ./output/n8n and ./output/audio are clean around each test."""
    for p in [Path("./output/n8n"), Path("./output/audio")]:
        if p.exists():
            shutil.rmtree(p)
    yield
    for p in [Path("./output/n8n"), Path("./output/audio")]:
        if p.exists():
            shutil.rmtree(p)


@pytest.fixture
def test_app(monkeypatch):
    # Import the app AFTER we’ve injected the fake module
    from app.main import app
    from app.services import tts_service

    # Mock TTS to avoid hitting Azure
    async def _fake_synth(self, text, outdir=None, save_vtt=None):
        return {
            "audio_path": "./output/audio/test/audio.mp3",
            "sentences_json_path": "./output/audio/test/sentences.json",
            "vtt_path": "./output/audio/test/subtitle.vtt",
        }

    monkeypatch.setattr(
        tts_service.TTSService, "synthesize", _fake_synth, raising=True
    )

    with TestClient(app) as client:
        yield client
