import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from LINELib import LineBot


BOT_ID = os.environ["LINEOA_BOT_ID"]
COOKIE_PATH = os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json")

bot = LineBot(cookie_path=COOKIE_PATH, ping_secs=30, max_stream_seconds=7200)


class CallbackHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/callback":
            self.send_error(404)
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(content_length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_error(400, "invalid JSON")
            return
        print("incoming webhook event count:", len(payload.get("events", [])))
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


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
    server = ThreadingHTTPServer(("127.0.0.1", 6100), CallbackHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        bot.listen(botid=BOT_ID)
    finally:
        server.shutdown()
        server.server_close()
