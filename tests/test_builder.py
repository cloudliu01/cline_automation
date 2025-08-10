# tests/test_builder.py
import os
import pytest

from app.services.builder import VideoBuilder

class _FakeMediaUtils:
    def __init__(self, audio_duration=2.0, video_duration=5.0):
        self._ad = audio_duration
        self._vd = video_duration

    def get_audio_info(self, _):
        return {"duration": self._ad}

    def get_video_info(self, _):
        # 仅用于视频背景时计算时长
        return {"duration": self._vd, "width": 320, "height": 240}

    def execute_ffmpeg_command(self, cmd, *_args, **_kwargs):
        # 模拟执行成功，并写出目标文件
        out = cmd[-1]
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"\x00" * 10)
        return True

def test_builder_requires_background_and_audio_for_image(tmp_path):
    b = VideoBuilder((320, 240))
    # 没设置背景 → 报错
    with pytest.raises(ValueError):
        b.build_command()

    # 背景是 image，但未设置 audio → 报错
    b.set_background_image(str(tmp_path/"bg.jpg"))
    with pytest.raises(ValueError):
        b.build_command()

def test_builder_image_with_audio_and_subs_builds_cmd(tmp_path):
    bg = tmp_path / "bg.jpg"
    bg.write_bytes(b"fake")  # 文件是否真实图像无所谓，这里只构建命令

    ass = tmp_path / "cap.ass"
    ass.write_text("[Script Info]\n; minimal\n")

    out = tmp_path / "out.mp4"
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"wav")

    b = VideoBuilder((320, 240))
    b.set_media_utils(_FakeMediaUtils(audio_duration=2.5))
    b.set_background_image(str(bg), effect_config={"effect": "ken_burns"})
    b.set_audio(str(audio))
    b.set_captions(str(ass))
    b.set_output_path(str(out))

    cmd = b.build_command()
    joined = " ".join(cmd)

    assert cmd[0] == "ffmpeg"
    assert str(bg) in joined
    assert str(audio) in joined
    assert "subtitles=" in joined
    assert str(out) == cmd[-1]
    # 有时长参数
    assert "-t" in cmd

def test_builder_video_background_without_audio_but_with_subs(tmp_path):
    bgv = tmp_path / "bg.mp4"
    bgv.write_bytes(b"fakevideo")
    ass = tmp_path / "cap.ass"
    ass.write_text("[Script Info]\n; minimal\n")
    out = tmp_path / "o.mp4"

    b = VideoBuilder((320, 240))
    b.set_media_utils(_FakeMediaUtils(video_duration=3.0))
    b.set_background_video(str(bgv))
    b.set_captions(str(ass))
    b.set_output_path(str(out))

    cmd = b.build_command()
    joined = " ".join(cmd)

    assert str(bgv) in joined
    assert "subtitles=" in joined
    assert str(out) == cmd[-1]

def test_execute_calls_mediautils_and_writes_file(tmp_path):
    bg = tmp_path / "bg.jpg"; bg.write_bytes(b"fake")
    audio = tmp_path / "a.wav"; audio.write_bytes(b"wav")
    out = tmp_path / "out.mp4"

    b = VideoBuilder((320, 240))
    b.set_media_utils(_FakeMediaUtils(audio_duration=1.0))
    b.set_background_image(str(bg))
    b.set_audio(str(audio))
    b.set_output_path(str(out))

    ok = b.execute()
    assert ok
    assert out.exists() and out.stat().st_size > 0
