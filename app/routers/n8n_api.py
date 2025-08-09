from __future__ import annotations

import os
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import RootModel

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

router = APIRouter(prefix="/n8n", tags=["N8N IO"])

OUTPUT_ROOT = Path("./output/n8n").resolve()


def _ensure_outdir() -> Path:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    return OUTPUT_ROOT


def _safe_write_json(rel_filename: str, data: Any) -> str:
    outdir = _ensure_outdir()
    path = (outdir / rel_filename).resolve()
    if not str(path).startswith(str(outdir)):
        raise HTTPException(status_code=403, detail="Invalid output path")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return str(path)


class GenericJSON(RootModel[Any]):
    """Accept arbitrary JSON payloads and echo back."""
    @property
    def data(self) -> Any:
        return self.root


@router.post("/parse_epub")
async def parse_epub(file: UploadFile = File(...)) -> List[Dict[str, str]]:
    if not file.filename or not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="Please upload an .epub file")

    # Save to a temp file, then use ebooklib to parse
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp:
        tmp_path = tmp.name
        content = await file.read()
        tmp.write(content)

    chapters: List[Dict[str, str]] = []
    try:
        book = epub.read_epub(tmp_path)
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            content = item.get_body_content()
            soup = BeautifulSoup(content, "html.parser")
            title_tag = soup.find(["h1", "h2"]) or soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else item.get_name()
            text = " ".join(p.get_text(strip=True) for p in soup.find_all("p"))
            chapters.append({"title": title, "text": text})
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # Write to ./output/n8n/chapters.json
    _safe_write_json("chapters.json", chapters)
    return chapters


@router.post("/upload")
async def upload_json(payload: GenericJSON):
    path = _safe_write_json("transcript_generated.json", payload.data)
    return {"status": "success", "path": path, "data": payload.data}


@router.post("/upload_kv_data")
async def upload_kv_data(payload: GenericJSON):
    path = _safe_write_json("kv_data.json", payload.data)
    return {"status": "success", "path": path, "data": payload.data}


@router.post("/upload_kv_data_revised")
async def upload_kv_data_revised(payload: GenericJSON):
    path = _safe_write_json("kv_data_revised.json", payload.data)
    return {"status": "success", "path": path, "data": payload.data}


@router.post("/upload_data_w_prompt")
async def upload_data_w_prompt(payload: GenericJSON):
    path = _safe_write_json("data_w_prompt.json", payload.data)
    return {"status": "success", "path": path, "data": payload.data}
