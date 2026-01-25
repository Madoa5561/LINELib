import os
from LINELib.linebot import LineBot

def example_send_image():
    bot_id = "U*****"
    chat_id = "C*****"
    file_path = "***.png"
    COOKIE_PATH = os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json")
    bot = LineBot(cookie_path=COOKIE_PATH)
    try:
        bot.sendFile(bot_id=bot_id, chat_id=chat_id, file_path=file_path)
    except Exception as e:
        print(e)

if __name__ == "__main__":
    example_send_image()
