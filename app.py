from flask import Flask, request, jsonify
from threading import Lock
import time
import os

from jiment_ai_generator import JimengAIGenerator

app = Flask(__name__)
jimeng_lock = Lock()
jimeng = JimengAIGenerator()  # Only one instance for now (singleton pattern)

@app.route('/clean_prompt', methods=['POST'])
def clean_prompt():
    with jimeng_lock:
        jimeng.clean_prompt()
    return jsonify({"status": "ok", "message": "Prompt cleaned"})

@app.route('/prompt', methods=['POST'])
def add_prompt():
    data = request.json
    content = data.get('content', '')
    with jimeng_lock:
        jimeng.clean_prompt()
        jimeng.add_prompt(content)
    return jsonify({"status": "ok", "message": "Prompt added", "prompt": content})

@app.route('/submit', methods=['POST'])
def submit():
    with jimeng_lock:
        jimeng.click_submit()
    return jsonify({"status": "ok", "message": "Submit button clicked"})

@app.route('/download', methods=['POST'])
def download_image():
    data = request.json
    index = int(data.get('index', 0))
    with jimeng_lock:
        jimeng.download_images(index)
    return jsonify({"status": "ok", "message": f"Download triggered for image {index}"})

@app.route('/refresh_images', methods=['POST'])
def refresh_images():
    with jimeng_lock:
        new_images = jimeng.get_all_available_images()
    return jsonify({"status": "ok", "new_images": len(new_images)})

@app.route('/download_new', methods=['POST'])
def download_new_images():
    with jimeng_lock:
        new_images = jimeng.download_new_images()
    return jsonify({"status": "ok", "new_images_downloaded": len(new_images)})

@app.route('/status', methods=['GET'])
def status():
    with jimeng_lock:
        img_count = len(jimeng.all_images_src)
    return jsonify({"status": "ok", "images_downloaded": img_count})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    with jimeng_lock:
        jimeng.close()
    return jsonify({"status": "ok", "message": "Generator closed."})


if __name__ == '__main__':
    # 只有主进程（不是 reloader 的子进程）才初始化
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        jimeng = JimengAIGenerator()
    app.run(host='0.0.0.0', port=5000, debug=True)
