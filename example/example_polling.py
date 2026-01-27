from LINELib.linebot import LineBot

bot = LineBot(
    cookie_path="lineoa-storage.json",
    ping_secs=30,
    email=None, # Auto selenium Input Option
    password=None # Auto selenium Input Option
)
BOT_ID = "U*****"

# メッセージ受信時
@bot.event
def on_message(event):
    payload = event.get('payload', {})
    chat_payload = payload.get('payload', {})
    message = chat_payload.get('message', {})
    text = message.get('text', '')
    print(f"[on_message] {text}")
    if message.get('type') == 'text' and text == "ping":
        bot.sendmessage( bot_id=payload.get('botId'), chat_id=payload.get('chatId'), text="pong!")

# botがグループに招待・参加
@bot.event
def on_join(event):
    payload = event.get('payload', {})
    bot_id = payload.get('botId')
    chat_id = payload.get('chatId')
    member = payload.get('payload', {}).get('members', {})
    print(chat_id, member)
    #print("[on_join]", event)

# botがグループから退会・キックされた
@bot.event
def on_leave(event):
    payload = event.get('payload', {})
    chat_id = payload.get('chatId')
    left_members = payload.get('payload', {}).get('left', {}).get('members', [])
    left_user_ids = [member.get('userId') for member in left_members]
    print(chat_id, left_user_ids)
    #print("[on_leave]", event)

# 誰かがグループに参加
@bot.event
def on_memberJoined(event):
    payload = event.get('payload', {})
    chat_id = payload.get('chatId')
    joined_members = payload.get('payload', {}).get('joined', {}).get('members', [])
    joined_user_ids = [member.get('userId') for member in joined_members]
    print(chat_id, joined_user_ids)
    #print("[on_memberJoined]", event)

# 誰かがグループから退出
@bot.event
def on_memberLeft(event):
    payload = event.get('payload', {})
    chat_id = payload.get('chatId')
    left_members = payload.get('payload', {}).get('left', {}).get('members', [])
    left_user_ids = [member.get('userId') for member in left_members]
    print(chat_id, left_user_ids)
    #print("[on_memberLeft]", event)

# メッセージが取り消された
@bot.event
def on_unsend(event):
    payload = event.get('payload', {})
    chat_id = payload.get('chatId')
    inner_payload = payload.get('payload', {})
    unsend_info = inner_payload.get('unsend', {})
    message_id = unsend_info.get('messageId')
    print(chat_id, message_id, unsend_info)
    #print("[on_unsend]", event)

# 誰かがbotのメッセージを既読
@bot.event
def on_chatRead(event):
    payload = event.get('payload', {})
    chat_id = payload.get('chatId')
    inner_payload = payload.get('payload', {})
    read_info = inner_payload.get('read', {})
    user_id = inner_payload.get('source', {}).get('userId')
    watermark = read_info.get('watermark')
    print(chat_id, user_id, watermark)
    #print("[on_chatRead]", event)

# その他のイベント
@bot.event
def on_unknown(event):
    pass
    #print("[unknown]", event)

if __name__ == "__main__":
    bot.listen(botid=BOT_ID)
