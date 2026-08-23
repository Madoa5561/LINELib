import os

from _login import create_bot


BOT_ID = os.environ["LINEOA_BOT_ID"]
bot = create_bot(ping_secs=30, max_stream_seconds=7200)


@bot.event
def on_init(event):
    print("init:", event.get("payload", {}).get("event"))


@bot.event
def on_ping(event):
    print("ping:", event.get("payload", {}).get("event"))


@bot.event
def on_message(event):
    normalized = bot.normalize_message_event(event)
    print("message:", normalized["message_type"], normalized.get("message_id"))

    if normalized.get("message_type") == "text" and normalized.get("text") == "ping":
        bot.sendMessage(
            bot_id=normalized["bot_id"],
            chat_id=normalized["chat_id"],
            text="pong",
        )

    if normalized.get("kind") == "media":
        path = f"./outputs/{normalized['message_id']}"
        saved = bot.save_message_media(event, path)
        print("saved media:", saved)


@bot.event
def on_unknown(event):
    print("unknown:", event.get("type"))


if __name__ == "__main__":
    bot.listen(botid=BOT_ID)
