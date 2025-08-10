# tests/test_media_api_video_generation.py
import os
import time
import json
import types

def _fake_captions():
    # 简单两句字幕
    return [
        {"text": "Hello", "start_ts": 0.00, "end_ts": 0.90},
        {"text": "World!", "start_ts": 0.90, "end_ts": 1.80},
    ]

def _patch_tts_and_stt_and_builder(monkeypatch, media_api_module):
    # 1) kokoro TTS：返回（字幕列表，...）
    def fake_kokoro(text, output_path, voice, speed):
        # 写个最简 wav 文件占位
        with open(output_path, "wb") as f:
            f.write(b"\x00" * 10)
        return (_fake_captions(), )

    monkeypatch.setattr(media_api_module.tts_manager, "kokoro", fake_kokoro, raising=True)

    # 2) STT：返回（字幕列表，时长）
    def fake_transcribe(audio_path, language=None):
        return (_fake_captions(), 1.8)
    monkeypatch.setattr(media_api_module.stt, "transcribe", fake_transcribe, raising=True)

    # 3) MediaUtils.get_video_info：用于背景图尺寸判断（这里把图片当“媒体”读尺寸）
    from PIL import Image
    class DummyMU:
        def get_video_info(self, path):
            try:
                with Image.open(path) as im:
                    w, h = im.size
            except Exception:
                w, h = (1080, 1920)
            return {"width": w, "height": h, "duration": 1.8}
    monkeypatch.setattr(media_api_module, "MediaUtils", DummyMU, raising=True)

    # 4) VideoBuilder.execute：不跑 ffmpeg，直接写输出文件
    def fake_execute(self):
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        with open(self.output_path, "wb") as f:
            f.write(b"\x00" * 10)
        return True
    from app.services import builder as builder_mod
    monkeypatch.setattr(builder_mod.VideoBuilder, "execute", fake_execute, raising=True)

def _wait_until_file(path, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return True
        time.sleep(0.02)
    return False

def test_generate_video_from_text_kokoro(client, media_api_module, upload_image, monkeypatch):
    _patch_tts_and_stt_and_builder(monkeypatch, media_api_module)

    bg_id = upload_image(w=320, h=240)

    # 触发文字->kokoro->字幕->合成视频
    form = {
        "background_id": bg_id,
        "text": "Hello World from kokoro TTS",
        "width": "320",
        "height": "240",
        "kokoro_voice": "af_heart",  # 有效 voice
        "kokoro_speed": "1.0",
        # 字幕配置（可选）
        "caption_config_line_count": "1",
        "caption_config_line_max_length": "20",
        "caption_config_font_size": "24",
        "caption_config_font_name": "Arial",
        "caption_config_font_bold": "true",
        "caption_config_font_italic": "false",
        "caption_config_font_color": "#ffffff",
        "caption_config_shadow_color": "#000000",
        "caption_config_stroke_color": "#000000",
        "caption_config_stroke_size": "2",
        "caption_config_shadow_blur": "4",
        "caption_config_shadow_transparency": "0.2",
        "caption_config_subtitle_position": "center",
        "caption_config_fade_ms": "0",
    }
    r = client.post("/video-tools/generate/tts-captioned-video", data=form)
    assert r.status_code == 200, r.text
    out_id = r.json()["file_id"]

    # 产物落在 Storage 里
    out_path = media_api_module.storage.get_media_path(out_id)
    assert _wait_until_file(out_path)
    assert out_path.endswith(".mp4")

def test_generate_video_from_existing_audio_id_stt(client, media_api_module, upload_image, upload_audio, monkeypatch):
    _patch_tts_and_stt_and_builder(monkeypatch, media_api_module)

    bg_id = upload_image()
    audio_id = upload_audio(1.2)

    # 触发 audio_id->STT->字幕->合成视频
    form = {
        "background_id": bg_id,
        "audio_id": audio_id,
        "width": "320",
        "height": "240",
        "kokoro_voice": "af_heart",  # 不会用到（因为提供了 audio_id），但参数校验通过
    }
    r = client.post("/video-tools/generate/tts-captioned-video", data=form)
    assert r.status_code == 200, r.text
    out_id = r.json()["file_id"]
    out_path = media_api_module.storage.get_media_path(out_id)
    assert _wait_until_file(out_path)

def test_generate_video_invalid_voice_returns_400(client, media_api_module, upload_image, monkeypatch):
    # 仅校验 voice，无需 patch 其它
    bg_id = upload_image()
    r = client.post(
        "/video-tools/generate/tts-captioned-video",
        data={
            "background_id": bg_id,
            "text": "abc",
            "width": "320",
            "height": "240",
            "kokoro_voice": "NOT_A_VALID_VOICE",
        },
    )
    assert r.status_code == 400
    assert "Invalid voice" in r.text

def test_generate_video_missing_background_returns_404(client, media_api_module):
    # 生成一个合法的 image 媒体 ID，但立刻删除底层文件，模拟“文件不存在”
    fake_id, fake_path = media_api_module.storage.create_media_filename_with_id(
        media_type="image", file_extension=".png"
    )
    if os.path.exists(fake_path):
        os.remove(fake_path)

    r = client.post(
        "/video-tools/generate/tts-captioned-video",
        data={
            "background_id": fake_id,   # 合法格式的 ID，比如 image_xxx.png
            "text": "abc",
            "width": "320",
            "height": "240",
            "kokoro_voice": "af_heart",
        },
    )
    assert r.status_code == 404
    assert "not found" in r.text.lower()
