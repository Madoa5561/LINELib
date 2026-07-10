import os
import threading
import time

from flask import Flask, request

from LINELib import LineBot


BOT_ID = os.environ["LINEOA_BOT_ID"]
COOKIE_PATH = os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json")

bot = LineBot(cookie_path=COOKIE_PATH, ping_secs=30, max_stream_seconds=7200)
app = Flask(__name__)


@app.post("/callback")
def callback():
    payload = request.get_json(force=True, silent=True) or {}
    print("incoming webhook payload:", payload)
    return {"ok": True}


@bot.event
def on_message(event):
    normalized = bot.normalize_message_event(event)
    if normalized.get("message_type") == "text" and normalized.get("text") == "ping":
        bot.sendMessage(
            bot_id=normalized["bot_id"],
            chat_id=normalized["chat_id"],
            text="pong from LINELib",
        )


if __name__ == "__main__":
    threading.Thread(target=app.run, kwargs={"port": 6100, "use_reloader": False}, daemon=True).start()
    bot.listen(botid=BOT_ID)
    while True:
        time.sleep(1)
