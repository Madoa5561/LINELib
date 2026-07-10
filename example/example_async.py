import asyncio
import os

from LINELib.LINELib import LINELib


async def main() -> None:
    cookie_path = os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json")
    bot_id = os.environ["LINEOA_BOT_ID"]
    chat_id = os.environ["LINEOA_CHAT_ID"]
    file_path = os.environ.get("LINEOA_FILE_PATH", "")

    lib = LINELib(storage=cookie_path)
    await lib.async_send_message(
        user_id=chat_id,
        context="LINELib async send_message",
        bot_id=bot_id,
    )
    if file_path:
        await lib.async_send_file(chat_id=chat_id, file_path=file_path, bot_id=bot_id)


if __name__ == "__main__":
    asyncio.run(main())
