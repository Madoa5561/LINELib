import os

from _login import create_bot


def main() -> None:
    bot_id = os.environ["LINEOA_BOT_ID"]
    chat_id = os.environ["LINEOA_CHAT_ID"]
    file_path = os.environ["LINEOA_FILE_PATH"]

    bot = create_bot()
    bot.sendFile(bot_id=bot_id, chat_id=chat_id, file_path=file_path)


if __name__ == "__main__":
    main()
