import os

from _login import create_bot


def main() -> None:
    bot_id = os.environ["LINEOA_BOT_ID"]
    chat_id = os.environ["LINEOA_CHAT_ID"]
    at_id = os.environ["LINEOA_AT_ID"]

    bot = create_bot()
    bot.create_and_send_flex(
        bot_id=bot_id,
        at_id=at_id,
        chat_id=chat_id,
        title="LINELib Flex example",
        image_url="https://example.com/image.jpg",
        tag_name="NEW",
        tag_color="info",
        description="Flex example from README and example directory.",
        action_label="Open",
        action_text="Open",
        delete_after_send=True,
    )


if __name__ == "__main__":
    main()
