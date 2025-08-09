# tests/test_n8n.py
import json
from pathlib import Path

import pytest


def test_upload_endpoints_write_files(test_app):
    payload = {"foo": "bar"}

    endpoints = [
        ("upload", "transcript_generated.json"),
        ("upload_kv_data", "kv_data.json"),
        ("upload_kv_data_revised", "kv_data_revised.json"),
        ("upload_data_w_prompt", "data_w_prompt.json"),
    ]

    for ep, filename in endpoints:
        r = test_app.post(f"/n8n/{ep}", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "success"
        path = Path(data["path"])
        assert path.exists()
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved == payload


def _epub_path() -> Path:
    # Resolve relative to this test file: tests/input_data/test1.epub
    return Path(__file__).parent / "input_data" / "think_and_grow_rich.epub"


def test_parse_epub_endpoint_creates_chapters_file(test_app):
    epub_file = _epub_path()
    if not epub_file.exists():
        pytest.skip(f"Missing EPUB fixture: {epub_file}")

    files = {"file": (epub_file.name, epub_file.read_bytes(), "application/epub+zip")}
    r = test_app.post("/n8n/parse_epub", files=files)
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


def test_parse_epub_rejects_non_epub(test_app):
    files = {"file": ("not_epub.txt", b"hello", "text/plain")}
    r = test_app.post("/n8n/parse_epub", files=files)
    assert r.status_code == 400
    assert "epub" in r.json()["detail"].lower()
