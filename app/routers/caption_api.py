from pathlib import Path
from typing import List, Literal, Optional, Tuple
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator


from app.services.caption import Caption, convert_webvtt_to_ass  # adjust import path if needed

router = APIRouter(prefix="/caption", tags=["Caption/Subtitle"])

# ----- Pydantic models
class Segment(BaseModel):
    text: List[str] = Field(..., description="Lines for this segment ('' allowed)")
    start_ts: float
    end_ts: float

class RenderSegmentsRequest(BaseModel):
    segments: List[Segment]
    width: int = 1920
    height: int = 1080
    output_path: Optional[str] = Field(
        None, description="If None, write under ./output/captions/<timestamp>.ass"
    )
    font_name: str = "Arial"
    font_size: int = 42
    font_color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_size: int = 2
    shadow_color: str = "#000000"
    shadow_transparency: float = 0.55  # 0 opaque..1 transparent
    shadow_blur: int = 3
    subtitle_position: Literal["top", "center", "bottom"] = "bottom"
    fade_ms: int = 120

    @field_validator("shadow_transparency")
    @classmethod
    def _clamp_alpha(cls, v):
        return max(0.0, min(1.0, v))

class RenderSegmentsResponse(BaseModel):
    ass_path: str

class VTTConvertRequest(BaseModel):
    vtt_text: str
    language_hint: Literal["auto", "en", "cjk"] = "auto"
    max_length_per_line: int = 22
    lines_per_segment: int = 2
    width: int = 1920
    height: int = 1080
    font_name: str = "Arial"
    font_size: int = 42
    font_color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_size: int = 2
    shadow_color: str = "#000000"
    shadow_transparency: float = 0.55
    shadow_blur: int = 3
    subtitle_position: Literal["top", "center", "bottom"] = "bottom"
    fade_ms: int = 120
    output_path: Optional[str] = None

    @field_validator("shadow_transparency")
    @classmethod
    def _clamp_alpha(cls, v):
        return max(0.0, min(1.0, v))

class VTTConvertResponse(BaseModel):
    ass_path: str

# ----- Helpers
def _default_outfile(prefix: str = "captions") -> Path:
    from datetime import datetime
    outdir = Path("./output") / prefix
    outdir.mkdir(parents=True, exist_ok=True)
    name = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".ass"
    return outdir / name

def _safe_in_output(path: Optional[str]) -> Path:
    if not path:
        return _default_outfile()
    p = Path(path).resolve()
    allowed = Path("./output").resolve()
    if not str(p).startswith(str(allowed)):
        raise HTTPException(status_code=403, detail="Output path must be under ./output")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

# ----- Endpoints

@router.post("/convert_vtt", response_model=VTTConvertResponse)
async def convert_vtt(req: VTTConvertRequest):
    outp = _safe_in_output(req.output_path)
    convert_webvtt_to_ass(
        vtt_text=req.vtt_text,
        output_path=str(outp),
        dimensions=(req.width, req.height),
        language_hint=req.language_hint,
        max_length_per_line=req.max_length_per_line,
        lines_per_segment=req.lines_per_segment,
        font_name=req.font_name,
        font_size=req.font_size,
        font_color=req.font_color,
        stroke_color=req.stroke_color,
        stroke_size=req.stroke_size,
        shadow_color=req.shadow_color,
        shadow_transparency=req.shadow_transparency,
        shadow_blur=req.shadow_blur,
        subtitle_position=req.subtitle_position,
        fade_ms=req.fade_ms,
    )
    return VTTConvertResponse(ass_path=str(outp))

@router.post("/render_segments", response_model=RenderSegmentsResponse)
async def render_segments(req: RenderSegmentsRequest):
    cp = Caption()
    outp = _safe_in_output(req.output_path)
    segments = [s.dict() for s in req.segments]

    cp.create_subtitle(
        segments=segments,
        dimensions=(req.width, req.height),
        output_path=str(outp),
        font_name=req.font_name,
        font_size=req.font_size,
        font_color=req.font_color,
        stroke_color=req.stroke_color,
        stroke_size=req.stroke_size,
        shadow_color=req.shadow_color,
        shadow_transparency=req.shadow_transparency,
        shadow_blur=req.shadow_blur,
        subtitle_position=req.subtitle_position,
        fade_ms=req.fade_ms,
    )
    return RenderSegmentsResponse(ass_path=str(outp))

@router.get("/file")
async def get_file(path: str):
    p = Path(path).resolve()
    allowed = Path("./output").resolve()
    if not str(p).startswith(str(allowed)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(p)
