# app/api/tts_kokoro.py
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Literal, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# 关键：直接用你的 TTS 实现，而不是 request.app.state.tts
from app.services.tts_kokoro import TTS, LANGUAGE_VOICE_MAP

router = APIRouter(prefix="/tts/kokoro", tags=["Kokoro TTS"])

# 单例，避免重复加载权重
_tts_engine = TTS()

# ---------- Models ----------

class KokoroSynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: str = "af_heart"          # e.g. "af_heart" (EN) or "zf_xiaobei" (ZH)
    speed: float = 1.0               # 0.5 ~ 1.5 typical
    outdir: str = "./output/audio"
    filename: Optional[str] = None   # if None -> auto timestamped
    save_vtt: bool = True
    save_captions_json: bool = True

class KokoroSynthesizeResponse(BaseModel):
    status: Literal["ok"]
    path: str
    duration: float
    sample_rate: int = 24000
    num_channels: int = 2
    captions_path: Optional[str] = None
    vtt_path: Optional[str] = None

# ---------- Helpers ----------

def _fmt_ts(ts: float) -> str:
    """seconds -> WebVTT timestamp (HH:MM:SS.mmm)"""
    if ts < 0:
        ts = 0.0
    hours = int(ts // 3600)
    minutes = int((ts % 3600) // 60)
    seconds = int(ts % 60)
    millis = int(round((ts - int(ts)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"

def _write_vtt(captions: List[dict], vtt_path: Path) -> None:
    lines = ["WEBVTT", ""]
    for i, c in enumerate(captions, 1):
        start_ts = _fmt_ts(float(c.get("start_ts", 0)))
        end_ts = _fmt_ts(float(c.get("end_ts", 0)))
        text = str(c.get("text", "")).strip()
        if not text:
            continue
        lines.append(str(i))
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(text)
        lines.append("")  # blank line between cues
    vtt_path.write_text("\n".join(lines), encoding="utf-8")

# ---------- Routes ----------

@router.post("/synthesize", response_model=KokoroSynthesizeResponse)
async def kokoro_synthesize(req: KokoroSynthesizeRequest):
    """
    Run Kokoro TTS and save outputs.
    根据 voice 自动选择 kokoro_english 或 kokoro_international。
    """
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    # voice 校验与语言判定
    voice = req.voice.strip()
    lang_code = LANGUAGE_VOICE_MAP.get(voice, {}).get("lang_code")
    if not lang_code:
        raise HTTPException(status_code=400, detail=f"Invalid voice: {voice}")

    # Prepare paths with audio/$YYYYMMDD_ddhhmm hierarchy
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    audio_subdir = Path("./") / date_str
    outdir = Path(req.outdir).resolve() / audio_subdir
    outdir.mkdir(parents=True, exist_ok=True)
    ts = now.strftime("%Y%m%d_%H%M%S")
    base = req.filename or f"kokoro_{voice}_{ts}.wav"
    wav_path = (outdir / base).with_suffix(".wav")
    captions_json_path = wav_path.with_suffix(".json")
    vtt_path = wav_path.with_suffix(".vtt")

    # Run TTS（不再使用 request.app.state.tts）
    try:
        if lang_code == "a":
            # 英文：带逐 token 时间戳
            captions, duration = _tts_engine.kokoro_english(text, str(wav_path), voice=voice, speed=req.speed)
        else:
            # 国际化（中文等）：按句子级别时间戳
            captions, duration = _tts_engine.kokoro_international(
                text, str(wav_path), voice=voice, lang_code=lang_code, speed=req.speed
            )
    except Exception as e:
        if "ordered_set" in str(e):
            raise HTTPException(
                status_code=500,
                detail="Missing dependency 'ordered_set'. Install with: pip install ordered-set",
            )
        raise HTTPException(status_code=500, detail=f"Kokoro synthesis failed: {e}")

    # Save optional sidecar files
    saved_captions = None
    saved_vtt = None
    try:
        if req.save_captions_json:
            captions_json_path.write_text(
                json.dumps(captions, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            saved_captions = str(captions_json_path)
        if req.save_vtt:
            _write_vtt(captions, vtt_path)
            saved_vtt = str(vtt_path)
    except Exception:
        # 不因副文件失败而整体报错
        pass

    return KokoroSynthesizeResponse(
        status="ok",
        path=str(wav_path),
        duration=float(duration),
        sample_rate=24000,
        num_channels=2,
        captions_path=saved_captions,
        vtt_path=saved_vtt,
    )

# Optional: safe-ish file serving under /output
@router.get("/file")
async def get_file(path: str):
    p = Path(path).resolve()
    allowed = Path("./output").resolve()
    if not str(p).startswith(str(allowed)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(p)
