from fastapi import APIRouter, Request
from app.models import PromptRequest, IndexRequest

router = APIRouter(prefix="/gen", tags=["Generator"])

@router.post("/clean_prompt")
async def clean_prompt(request: Request):
    await request.app.state.gen.clean_prompt()
    return {"status": "ok", "message": "Prompt cleaned"}

@router.post("/prompt")
async def add_prompt(request: Request, req: PromptRequest):
    await request.app.state.gen.clean_prompt()
    await request.app.state.gen.add_prompt(req.content)
    return {"status": "ok", "message": "Prompt added", "prompt": req.content}

@router.post("/submit")
async def submit(request: Request):
    await request.app.state.gen.click_submit()
    return {"status": "ok", "message": "Submit button clicked"}

@router.post("/download")
async def download_image(request: Request, req: IndexRequest):
    await request.app.state.gen.download_images(req.index)
    return {"status": "ok", "message": f"Download triggered for image {req.index}"}

@router.post("/refresh_images")
async def refresh_images(request: Request):
    new_images = await request.app.state.gen.get_all_available_images()
    return {"status": "ok", "new_images": len(new_images)}

@router.post("/download_new")
async def download_new_images(request: Request):
    new_images = await request.app.state.gen.download_new_images()
    return {"status": "ok", "new_images_downloaded": len(new_images)}

@router.get("/status")
async def status(request: Request):
    img_count = len(request.app.state.gen.all_images_src)
    return {"status": "ok", "images_downloaded": img_count}