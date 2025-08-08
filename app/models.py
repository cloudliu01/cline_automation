from pydantic import BaseModel, Field
from typing import Optional

class PromptRequest(BaseModel):
    content: str = Field(..., description="Prompt text to add")

class IndexRequest(BaseModel):
    index: int = 0

class TTSSynthesizeRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize")
    save_vtt: bool = True
    outdir: str = "./output/audio"

class TTSSynthesizeResponse(BaseModel):
    audio_path: str
    sentences_json_path: str
    vtt_path: Optional[str]