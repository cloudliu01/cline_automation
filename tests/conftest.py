# tests/conftest.py
import sys
import types
import shutil
import pytest
import io
import wave
import importlib
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pathlib import Path


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



@pytest.fixture()
def tmp_media_dir(tmp_path):
    d = tmp_path / "media"
    (d / "image").mkdir(parents=True, exist_ok=True)
    (d / "video").mkdir(parents=True, exist_ok=True)
    (d / "audio").mkdir(parents=True, exist_ok=True)
    (d / "tmp").mkdir(parents=True, exist_ok=True)
    return str(d)

@pytest.fixture()
def media_api_module(tmp_media_dir, monkeypatch):
    """
    以独立 FastAPI 应用加载 media_api，并把其 module 级别单例
    (storage/tts_manager/stt 等) 指向可测试的对象。
    """
    mod = importlib.import_module("app.routers.media_api")

    # 覆盖 Storage 根目录
    from app.services.storage import Storage
    mod.storage = Storage(storage_path=tmp_media_dir)

    return mod

@pytest.fixture()
def app(media_api_module):
    app = FastAPI()
    app.include_router(media_api_module.v1_media_api_router, prefix="")
    return app

@pytest.fixture()
def client(app):
    return TestClient(app)

# ---------- 一些小工具 ----------
def _make_png_bytes(w=64, h=64, color=(200, 180, 120)):
    im = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    buf.seek(0)
    return buf

def _make_wav_bytes(duration_sec=1.0, sample_rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)   # 16-bit
        wf.setframerate(sample_rate)
        nframes = int(duration_sec * sample_rate)
        wf.writeframes(b"\x00\x00" * nframes)
    buf.seek(0)
    return buf

@pytest.fixture()
def upload_image(client):
    def _do(w=64, h=64):
        png = _make_png_bytes(w, h)
        files = {"file": ("bg.png", png, "image/png")}
        resp = client.post(
            "/storage",
            data={"media_type": "image"},
            files=files,
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["file_id"]
    return _do

@pytest.fixture()
def upload_audio(client):
    def _do(seconds=1.0):
        wav = _make_wav_bytes(seconds)
        files = {"file": ("a.wav", wav, "audio/wav")}
        resp = client.post(
            "/storage",
            data={"media_type": "audio"},
            files=files,
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["file_id"]
    return _do
