import asyncio
import os

from _login import create_library


async def main() -> None:
    bot_id = os.environ["LINEOA_BOT_ID"]
    chat_id = os.environ["LINEOA_CHAT_ID"]
    file_path = os.environ.get("LINEOA_FILE_PATH", "")

    lib = create_library()
    await lib.async_send_message(
        user_id=chat_id,
        context="LINELib async send_message",
        bot_id=bot_id,
    )
    if file_path:
        await lib.async_send_file(chat_id=chat_id, file_path=file_path, bot_id=bot_id)


if __name__ == "__main__":
    asyncio.run(main())
