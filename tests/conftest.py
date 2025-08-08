import sys
import types
import asyncio
import builtins
import pytest
from fastapi.testclient import TestClient

# Before importing app.main, inject a fake jiment_ai_generator_async module so lifespan won't touch a real browser.
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

    async def add_prompt(self, content):
        self.prompts.append(content)

    async def click_submit(self):
        self.submits += 1

    async def download_images(self, index:int):
        self.downloaded.append(index)

    async def get_all_available_images(self):
        self.refreshed += 1
        return ["img1", "img2"]

    async def download_new_images(self):
        self.new_downloads += 2
        return ["imgA", "imgB"]


@pytest.fixture(scope="session")
def fake_gen_module():
    m = types.ModuleType("jiment_ai_generator_async")
    m.JimengAIGenerator = _FakeGen
    sys.modules["jiment_ai_generator_async"] = m
    return m

@pytest.fixture
def test_app(fake_gen_module, monkeypatch):
    # Import after monkeypatching the generator module
    from app.main import app
    # Patch TTSService.synthesize to return a deterministic result
    from app.services import tts_service
    async def _fake_synth(self, text, outdir=None, save_vtt=None):
        return {
        "audio_path": "./output/audio/test/audio.mp3",
        "sentences_json_path": "./output/audio/test/sentences.json",
        "vtt_path": "./output/audio/test/subtitle.vtt"
    }

    monkeypatch.setattr(tts_service.TTSService, "synthesize", _fake_synth, raising=True)
    # Provide TestClient which will run lifespan (using _FakeGen)
    with TestClient(app) as client:
        yield client