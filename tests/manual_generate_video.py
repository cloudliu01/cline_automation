import os
import glob
from app.services.builder import VideoBuilder
from app.services.media import MediaUtils

if __name__ == "__main__":
    images_dir = "output/audio/20250809_215722"
    exts = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp")
    background_images = []
    for pat in exts:
        background_images.extend(sorted(glob.glob(os.path.join(images_dir, pat))))
    if not background_images:
        raise SystemExit(f"No images found under {images_dir}")

    audio_file = "output/audio/20250809_215722/audio.mp3"
    captions_file = "output/audio/20250809_215722/out.ass"
    output_file = "output/audio/20250809_215722/output_multi.mp4"
    dimensions = (1920, 1080)

    # Either specify explicit durations...
    # image_durations = [2.5, 3.0, 2.0, 4.0][:len(background_images)]
    # ...or let the builder split by audio duration:
    image_durations = [5, 5, 5, 30]

    builder = VideoBuilder(dimensions=dimensions)
    builder.set_media_utils(MediaUtils())
    builder.set_background_images(
        background_images,
        effect_config={"effect": "ken_burns", "zoom_factor": 0.001, "direction": "zoom-to-top-left"},
        image_durations=image_durations,   # <-- changed
    )
    builder.set_audio(audio_file)
    builder.set_captions(captions_file)
    builder.set_output_path(output_file)

    print("开始生成视频...")
    print("Images:", len(background_images))
    success = builder.execute()
    print("✅ 成功" if success else "❌ 失败")
