import os
import glob
from app.services.slideshow_orchestrator import MultiImageVideoBuilder

if __name__ == "__main__":
    # Inputs
    images_dir = "output/audio/20250809_215722"
    audio_file = "output/audio/20250809_215722/audio.mp3"
    captions_file = "output/audio/20250809_215722/out.ass"
    output_file = "output/audio/20250809_215722/output_multi.mp4"

    # Collect images
    exts = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp")
    images = []
    for pat in exts:
        images.extend(sorted(glob.glob(os.path.join(images_dir, pat))))
    if not images:
        raise SystemExit(f"No images found under {images_dir}")

    # Per-image durations (seconds). If None -> split evenly by full audio length.
    image_durations = None
    # Example:
    image_durations = [10, 10, 10, 20][:len(images)]

    builder = MultiImageVideoBuilder(dimensions=(1920, 1080))
    ok = builder.build(
        images=images,
        audio_file=audio_file,          # required if image_durations is None
        captions_file=captions_file,    # None to skip captions
        output_file=output_file,
        image_durations=image_durations,
        effect_config={"effect": "ken_burns", "zoom_factor": 0.001, "direction": "zoom-to-top-left"},
        # effect_configs=[ ... ]  # optional per-image effects
        keep_temps=False,
    )
    print("✅ Done" if ok else "❌ Failed")