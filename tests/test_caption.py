import pytest
from pathlib import Path
from app.services.caption import Caption, convert_webvtt_to_ass


def test_is_punctuation_catches_cjk():
    cp = Caption()
    assert cp.is_punctuation("，")
    assert cp.is_punctuation("。")
    assert cp.is_punctuation("!?")
    assert not cp.is_punctuation("啊")
    assert not cp.is_punctuation("A")

def test_override_alpha_and_color(tmp_path: Path):
    cp = Caption()
    segs = [{"text": ["测试", "第二行"], "start_ts": 0.0, "end_ts": 2.0}]
    out = tmp_path / "x.ass"
    cp.create_subtitle(
        segs, (1280, 720), str(out),
        shadow_color="#112233",
        shadow_transparency=0.5,  # \1a should be ~7F/80
        shadow_blur=2,
        fade_ms=100,
    )
    t = out.read_text(encoding="utf-8")
    # \1c should be &HBBGGRR& with NO alpha
    assert "\\1c&H332211&" in t
    # \1a should be &HAA& where AA ≈ 127..128
    assert "\\1a&H7F&" in t or "\\1a&H80&" in t
    # Fade tag present
    assert "\\fad(100,100)" in t

def test_convert_webvtt_to_ass(tmp_path: Path):
    vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n这是一个测试。\n"
    out = tmp_path / "o.ass"
    p = convert_webvtt_to_ass(
        vtt_text=vtt,
        output_path=str(out),
        dimensions=(800, 600),
        language_hint="cjk",
        max_length_per_line=8,
        lines_per_segment=2,
        fade_ms=80,
    )
    assert Path(p).exists()
    txt = Path(p).read_text(encoding="utf-8")
    assert "[Events]" in txt and "\\pos(" in txt
