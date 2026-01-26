from LINELib.linebot import LineBot
import os

def example_send_text():
    bot_id = "U***"
    chat_id = "C***"
    COOKIE_PATH = os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json")
    bot = LineBot(cookie_path=COOKIE_PATH)
    try:
        bot.sendMessage(bot_id=bot_id, chat_id=chat_id, text="lineoaからのテストメッセージ")
    except Exception as e:
        print(e)

if __name__ == "__main__":
    example_send_text()
