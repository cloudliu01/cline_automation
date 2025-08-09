from faster_whisper import WhisperModel
import sys
from pathlib import Path
from loguru import logger
from app.services.config import device, whisper_model, whisper_compute_type

class STT:
    def __init__(self):
        self.model = WhisperModel(
            model_size_or_path=whisper_model, 
            compute_type=whisper_compute_type
        )

    def transcribe(self, audio_path, language = None, beam_size=5):
        logger.bind(
            device=device.type,
            model_size=whisper_model,
            compute_type=whisper_compute_type,
            audio_path=audio_path,
            language=language,
        ).debug(
            "transcribing audio with Whisper model",
        )
        segments, info = self.model.transcribe(
            audio_path,
            beam_size=beam_size,
            word_timestamps=True,
            language=language,
        )

        duration = info.duration
        captions = []
        for segment in segments:
            for word in segment.words:
                captions.append(
                    {
                        "text": word.word,
                        "start_ts": word.start,
                        "end_ts": word.end,
                    }
                )
        return captions, duration


if __name__ == "__main__":

    # If an MP3 file path is passed as an argument, use it; otherwise use a default test file
    if len(sys.argv) > 1:
        mp3_path = Path(sys.argv[1])
    else:
        mp3_path = Path("test.mp3")  # Replace with a small sample file path

    if not mp3_path.exists():
        print(f"Error: MP3 file not found: {mp3_path}")
        sys.exit(1)

    stt = STT()
    captions, duration = stt.transcribe(str(mp3_path))

    print(f"Duration: {duration:.2f} seconds")
    print("Captions:")
    for c in captions:
        print(f"[{c['start_ts']:.2f} - {c['end_ts']:.2f}] {c['text']}")
