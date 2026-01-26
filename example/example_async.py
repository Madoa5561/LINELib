import asyncio
import os
from LINELib.LINELib import LINELib

async def async_send_examples():
    COOKIE_PATH = os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json")
    lib = LINELib(storage=COOKIE_PATH)
    bot_id = "U****"
    chat_id = "C***"
    try:
        res = await lib.async_send_message(user_id=chat_id, context="lineoaからの非同期テストメッセージ", bot_id=bot_id)
        print("async send_message result:", res)
    except Exception as e:
        print("async send_message error:", e)
    file_path = os.environ.get("EXAMPLE_FILE_PATH", "logo.png")
    if os.path.exists(file_path):
        try:
            fres = await lib.async_send_file(chat_id=chat_id, file_path=file_path, bot_id=bot_id)
            print("async send_file result:", fres)
        except Exception as e:
            print("async send_file error:", e)

if __name__ == "__main__":
    asyncio.run(async_send_examples())
