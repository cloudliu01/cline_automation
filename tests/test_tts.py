from pathlib import Path

def test_tts_synthesize_returns_paths(test_app, tmp_path, monkeypatch):
    # Ensure output dir exists for the fake paths (not strictly required since we return JSON)
    out = Path("./output/audio/test")
    out.mkdir(parents=True, exist_ok=True)
    (out / "audio.mp3").write_bytes(b"fake")
    (out / "sentences.json").write_text("[]", encoding="utf-8")
    (out / "subtitle.vtt").write_text("WEBVTT", encoding="utf-8")

    r = test_app.post("/tts/synthesize", json={
        "text": "hello tts",
        "save_vtt": True,
        "outdir": "./output/audio"
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert "audio_path" in data and data["audio_path"].endswith("audio.mp3")
    assert "sentences_json_path" in data
    assert "vtt_path" in data and data["vtt_path"].endswith(".vtt")

def test_tts_file_security_allows_output_only(test_app, tmp_path):
    # Allowed
    good = Path("./output/ok.txt").resolve()
    good.parent.mkdir(parents=True, exist_ok=True)
    good.write_text("ok", encoding="utf-8")
    r = test_app.get(f"/tts/file?path={good}")
    assert r.status_code == 200

    # Disallowed (escape out of ./output)
    bad = tmp_path / "hacker.txt"
    bad.write_text("nope", encoding="utf-8")
    r = test_app.get(f"/tts/file?path={bad}")
    assert r.status_code == 403