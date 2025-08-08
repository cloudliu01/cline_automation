from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routers import gen, tts_api, n8n
from jiment_ai_generator_async import JimengAIGenerator  # existing dependency
from app.services.tts_service import TTSService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize long-lived services
    app.state.gen = JimengAIGenerator()
    await app.state.gen.start()
    app.state.tts = TTSService()  # thin async wrapper around your tts.synthesize_speech()
    try:
        yield
    finally:
        await app.state.gen.close()

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, title="Media Automation API", version="1.0.0")
    app.include_router(gen.router)
    app.include_router(tts_api.router)
    app.include_router(n8n.router)
    return app

app = create_app()

# Run with: uvicorn app.main:app --reload