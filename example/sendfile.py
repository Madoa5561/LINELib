import os
from LINELib import LINELib

def example_send_image():
    bot_id = "U*********"
    chat_id = "C*******"
    file_path = "./*****.zip" 
    COOKIE_PATH = os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json")
    client = LINELib(storage=COOKIE_PATH)
    try:
        result = client.send_file(bot_id, chat_id, file_path)
    except Exception as e:
        print(e)

if __name__ == "__main__":
    example_send_image()
