from flask import Flask, request, jsonify
from LINELib.LINELib import LINELib, LINEOAError
import os
import werkzeug

app = Flask(__name__)

COOKIE_PATH = os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json")
client = LINELib(storage=COOKIE_PATH)

@app.route("/send", methods=["POST"])
def send_message():
    data = request.json
    user_id = data.get("user_id")
    text = data.get("text")
    bot_id = data.get("bot_id")
    if not user_id or not text:
        return jsonify({"error": "user_id and text are required"}), 400
    try:
        result = client.send_message(user_id, text, bot_id=bot_id)
        return jsonify({"result": result})
    except LINEOAError as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sendImage", methods=["POST"])
def send_image():
    data = request.form
    chat_id = data.get("chat_id")
    bot_id = data.get("bot_id")
    if "image" not in request.files:
        return jsonify({"error": "image file required"}), 400
    image_file = request.files["image"]
    tmp_path = os.path.join("/tmp", werkzeug.utils.secure_filename(image_file.filename))
    image_file.save(tmp_path)
    try:
        result = client.send_image(chat_id, tmp_path, bot_id=bot_id)
        os.remove(tmp_path)
        return jsonify({"result": result})
    except LINEOAError as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return jsonify({"error": str(e)}), 500

@app.route("/bots", methods=["GET"])
def get_bots():
    try:
        bots = client.bots.ids
        return jsonify(bots)
    except LINEOAError as e:
        return jsonify({"error": str(e)}), 500

@app.route("/chats", methods=["GET"])
def get_chats():
    try:
        chats = client.chats.ids
        return jsonify(chats)
    except LINEOAError as e:
        return jsonify({"error": str(e)}), 500

@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
