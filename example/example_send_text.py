import os

from _login import create_bot


def main() -> None:
    bot_id = os.environ["LINEOA_BOT_ID"]
    chat_id = os.environ["LINEOA_CHAT_ID"]

    bot = create_bot()
    bot.sendMessage(
        bot_id=bot_id,
        chat_id=chat_id,
        text="LINELib からのテキスト送信テスト",
    )


if __name__ == "__main__":
    main()
