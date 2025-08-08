# tests/test_gen.py
def test_gen_prompt_flow(test_app):
    # clean prompt
    r = test_app.post("/gen/clean_prompt")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # add prompt
    r = test_app.post("/gen/prompt", json={"content": "hello world"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["prompt"] == "hello world"

    # submit
    r = test_app.post("/gen/submit")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # refresh images (fake returns 2)
    r = test_app.post("/gen/refresh_images")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["new_images"] == 2

    # download new (fake returns 2)
    r = test_app.post("/gen/download_new")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["new_images_downloaded"] == 2

    # download a specific index
    r = test_app.post("/gen/download", json={"index": 1})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # status reflects the fake's two images
    r = test_app.get("/gen/status")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["images_downloaded"] == 2
