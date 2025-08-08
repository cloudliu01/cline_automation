from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from app.models import TTSSynthesizeRequest, TTSSynthesizeResponse

router = APIRouter(prefix="/tts", tags=["Text-to-Speech"])

@router.post("/synthesize", response_model=TTSSynthesizeResponse)
async def synthesize(req: TTSSynthesizeRequest, request: Request):
    result = await request.app.state.tts.synthesize(
        text=req.text, outdir=req.outdir, save_vtt=req.save_vtt
    )
    return result

@router.get("/file")
async def get_file(path: str):
    # Basic, safe-ish file serving limited to the /output directory
    p = Path(path).resolve()
    allowed = Path("./output").resolve()
    if not str(p).startswith(str(allowed)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(p)