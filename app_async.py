import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from pydantic import BaseModel

from jiment_ai_generator_async import JimengAIGenerator

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.gen = JimengAIGenerator()
    await app.state.gen.start()
    yield
    await app.state.gen.close()

app = FastAPI(lifespan=lifespan)

class PromptRequest(BaseModel):
    content: str

@app.post("/clean_prompt")
async def api_clean_prompt(request: Request):
    await request.app.state.gen.clean_prompt()
    return {"status": "ok", "message": "Prompt cleaned"}

@app.post("/prompt")
async def api_add_prompt(request: Request, req: PromptRequest):
    await request.app.state.gen.clean_prompt()
    await request.app.state.gen.add_prompt(req.content)
    return {"status": "ok", "message": "Prompt added", "prompt": req.content}

@app.post("/submit")
async def api_submit(request: Request):
    await request.app.state.gen.click_submit()
    return {"status": "ok", "message": "Submit button clicked"}

@app.post("/download")
async def api_download_image(request: Request):
    data = await request.json()
    index = int(data.get('index', 0))
    await request.app.state.gen.download_images(index)
    return {"status": "ok", "message": f"Download triggered for image {index}"}

@app.post("/refresh_images")
async def api_refresh_images(request: Request):
    new_images = await request.app.state.gen.get_all_available_images()
    return {"status": "ok", "new_images": len(new_images)}

@app.post("/download_new")
async def api_download_new_images(request: Request):
    new_images = await request.app.state.gen.download_new_images()
    return {"status": "ok", "new_images_downloaded": len(new_images)}

@app.get("/status")
async def api_status(request: Request):
    img_count = len(request.app.state.gen.all_images_src)
    return {"status": "ok", "images_downloaded": img_count}
