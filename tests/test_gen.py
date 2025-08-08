def test_gen_prompt_flow(test_app):
    # Clean prompt
    r = test_app.post("/gen/clean_prompt")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # Add prompt
    r = test_app.post("/gen/prompt", json={"content": "hello world"})
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert j["prompt"] == "hello world"

    # Submit
    r = test_app.post("/gen/submit")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # Refresh images
    r = test_app.post("/gen/refresh_images")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["new_images"] == 2

    # Download new
    r = test_app.post("/gen/download_new")
    assert r.status_code == 200
    assert r.json()["new_images_downloaded"] == 2

    # Download index
    r = test_app.post("/gen/download", json={"index": 1})
    assert r.status_code == 200
    assert "image 1" in r.json()["message"]

    # Status
    r = test_app.get("/gen/status")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "images_downloaded" in r.json()