import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_output_dir():
    """Ensure ./output/n8n is empty before and after each test."""
    outdir = Path("./output/n8n")
    if outdir.exists():
        shutil.rmtree(outdir)
    yield
    if outdir.exists():
        shutil.rmtree(outdir)


def test_upload_endpoints_write_files():
    payload = {"foo": "bar"}

    endpoints = [
        ("upload", "transcript_generated.json"),
        ("upload_kv_data", "kv_data.json"),
        ("upload_kv_data_revised", "kv_data_revised.json"),
        ("upload_data_w_prompt", "data_w_prompt.json"),
    ]

    for ep, filename in endpoints:
        r = client.post(f"/api/{ep}", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "success"
        path = Path(data["path"])
        assert path.exists()
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved == payload


def _epub_path() -> Path:
    # Resolve relative to this test file: tests/input_data/think_and_grow_rich.epub
    return Path(__file__).parent / "input_data" / "think_and_grow_rich.epub"


def test_parse_epub_endpoint_creates_chapters_file():
    epub_file = _epub_path()
    if not epub_file.exists():
        pytest.skip(f"Missing EPUB fixture: {epub_file}")

    files = {"file": (epub_file.name, epub_file.read_bytes(), "application/epub+zip")}
    r = client.post("/api/parse_epub", files=files)
    assert r.status_code == 200, r.text
    chapters = r.json()
    assert isinstance(chapters, list)
    assert len(chapters) >= 1
    assert isinstance(chapters[0].get("title", ""), str)
    assert isinstance(chapters[0].get("text", ""), str)

    outpath = Path("./output/n8n/chapters.json")
    assert outpath.exists()
    saved = json.loads(outpath.read_text(encoding="utf-8"))
    assert saved == chapters


def test_parse_epub_rejects_non_epub():
    files = {"file": ("not_epub.txt", b"hello", "text/plain")}
    r = client.post("/api/parse_epub", files=files)
    assert r.status_code == 400
    assert "epub" in r.json()["detail"].lower()
