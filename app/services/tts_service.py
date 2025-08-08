import asyncio
from functools import partial
from typing import Any, Dict

# Reuse your existing implementation from tts.py
from app.services.tts import synthesize_speech

class TTSService:
    """Async wrapper around the blocking synthesize_speech() function."""
    def __init__(self, default_outdir: str = "./output/audio", default_save_vtt: bool = True):
        self.default_outdir = default_outdir
        self.default_save_vtt = default_save_vtt

    async def synthesize(self, text: str, outdir: str | None = None, save_vtt: bool | None = None) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        fn = partial(
            synthesize_speech,
            text=text,
            outdir=outdir or self.default_outdir,
            save_vtt=self.default_save_vtt if save_vtt is None else save_vtt,
        )
        return await loop.run_in_executor(None, fn)