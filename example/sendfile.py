import os

from LINELib.linebot import LineBot


def main() -> None:
    cookie_path = os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json")
    bot_id = os.environ["LINEOA_BOT_ID"]
    chat_id = os.environ["LINEOA_CHAT_ID"]
    file_path = os.environ["LINEOA_FILE_PATH"]

    bot = LineBot(cookie_path=cookie_path)
    bot.sendFile(bot_id=bot_id, chat_id=chat_id, file_path=file_path)


if __name__ == "__main__":
    main()
