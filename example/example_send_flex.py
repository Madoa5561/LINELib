from LINELib import LineBot
import time

BOT_ID = "U352****"
AT_ID  = "318pgxfs"   # @なし
CHAT_ID = "U2aa9b****"

bot = LineBot(cookie_path="lineoa-storage.json", ping_secs=30)

@bot.event
def on_message(event):
    payload = event.get("payload", {})
    sub     = payload.get("payload", {})
    chat_id = sub.get("chatId") or payload.get("chatId")
    bot_id  = sub.get("botId")  or payload.get("botId")
    msg     = sub.get("message", {})
    msg_id  = msg.get("id")
    msg_ts  = msg.get("createdAt")

    if not (chat_id and bot_id):
        return

    bot._lib._chat_service.create_and_send_flex(
        bot_id=bot_id,
        at_id=AT_ID,
        chat_id=chat_id,
        title="商品名",
        image_url="https://card-type-message.line-scdn.net/card-type-message-image-2026/318ogzps/1781426089651-VppcArdKbk6dtLEGMAJFuGgasa2d4KfSsBcbR6G6JRwecpO1Jp",
        tag_name="NEW",
        tag_color="info",
        description="商品の説明文",
        action_label="詳しく見る",
        action_text="詳しく見る",
        delete_after_send=True, #送信後にカードを削除する 
        session=bot._session,
        xsrf_token=bot._xsrf_token,
    )
    print(f"[{chat_id}] Flex 送信完了")

    #既読
    if msg_id:
        ts = int(msg_ts) if msg_ts else int(time.time() * 1000)
        bot._lib._chat_service.mark_as_read(
            bot_id=bot_id,
            chat_id=chat_id,
            message_id=msg_id,
            timestamp=ts,
            session=bot._session,
            xsrf_token=bot._xsrf_token,
        )

bot.listen(BOT_ID)
