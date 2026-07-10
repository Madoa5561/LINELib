import json
import os

from LINELib import LineBot


def main() -> None:
    cookie_path = os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json")
    bot = LineBot(cookie_path=cookie_path)

    event_path = os.environ["LINEOA_EVENT_JSON"]
    with open(event_path, "r", encoding="utf-8") as f:
        event = json.load(f)

    normalized = bot.normalize_message_event(event)
    print(normalized)

    if normalized.get("message_type") == "link":
        saved = bot.save_message_media(event, "./outputs/link_message")
    else:
        saved = bot.save_message_media(event, f"./outputs/{normalized.get('message_id', 'message')}")
    print("saved:", saved)


if __name__ == "__main__":
    main()
