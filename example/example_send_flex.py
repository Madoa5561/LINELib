import os

from LINELib.linebot import LineBot


def main() -> None:
    cookie_path = os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json")
    bot_id = os.environ["LINEOA_BOT_ID"]
    chat_id = os.environ["LINEOA_CHAT_ID"]
    at_id = os.environ["LINEOA_AT_ID"]

    bot = LineBot(cookie_path=cookie_path)
    bot._lib._chat_service.create_and_send_flex(
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
        session=bot._session,
        xsrf_token=bot._xsrf_token,
    )


if __name__ == "__main__":
    main()
