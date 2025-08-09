from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/stt", tags=["Speech-to-Text"])

# ----- Pydantic models (inline to keep this router self-contained)
class STTWord(BaseModel):
    text: str
    start_ts: float
    end_ts: float

class STTTranscribeRequest(BaseModel):
    audio_path: str = Field(..., description="Server-accessible path to audio file")
    language: Optional[str] = Field(None, description="ISO code, e.g. 'en', 'zh'")
    beam_size: int = Field(5, ge=1, le=10)

class STTTranscribeResponse(BaseModel):
    duration: float
    captions: List[STTWord]

@router.post("/transcribe", response_model=STTTranscribeResponse)
async def transcribe(req: STTTranscribeRequest, request: Request):
    """
    Transcribe an audio file using the STT service (app.state.stt).
    Expects the STT service compatible with stt.py's STT.transcribe(audio_path,...)
    """
    # Basic path validation
    p = Path(req.audio_path).resolve()
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Audio not found: {p}")

    # Prefer app.state.stt if present; else import on-demand
    stt_service = getattr(request.app.state, "stt", None)
    if stt_service is None:
        # Lazy import fallback
        from app.routers.stt_api import STT  # adjust if your module path differs
        stt_service = STT()
        # (Optional) cache it
        request.app.state.stt = stt_service

    captions, duration = stt_service.transcribe(
        audio_path=str(p),
        language=req.language,
        beam_size=req.beam_size,
    )

    return STTTranscribeResponse(duration=duration, captions=captions)

@router.get("/file")
async def get_file(path: str):
    # Safe-ish file serving limited to ./output
    p = Path(path).resolve()
    allowed = Path("./output").resolve()
    if not str(p).startswith(str(allowed)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(p)
