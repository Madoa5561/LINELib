import sys
import logging
import threading
from argparse import ArgumentParser
from flask import Flask, request, abort, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix
import requests
from LINELib.util import (
    link_group_and_chat,
    get_chatid_from_groupid,
    get_groupid_from_chatid
)
from LINELib.linebot import LineBot

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    JoinEvent,
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ApiException,
)
bot = LineBot(
    cookie_path="lineoa-storage.json",
    ping_secs=20
)


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app.logger.setLevel(logging.INFO)
pending_groupids = {}
pending_chatids = {}

BOT_ID = "U*****"
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)

if channel_secret is None or channel_access_token is None:
    print('Specify LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN as environment variables.')
    sys.exit(1)

handler = WebhookHandler(channel_secret)
configuration = Configuration(
    access_token=channel_access_token
)


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except ApiException as e:
        app.logger.warn("Got exception from LINE Messaging API: %s\n" % e.body)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    text = event.message.text
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        if text == 'ping':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text='pong from linesdk!'),
                    ]
                )
            )
            bot.sendMessage(
                bot_id="Ue7ffdf8230e5ffe2ac073b09ce44e17d",
                chat_id=get_chatid_from_groupid(event.source.group_id),
                text="pong from LINELib!"
            )

#######################################
@bot.event
def on_join(event):
    payload = event.get('payload', {})
    chat_id = payload.get('chatId')
    print(f"chat_id: {chat_id} LINELib EVENT on_join")
    print("pending_groupids before:", pending_groupids)
    linked = False
    for group_id in list(pending_groupids):
        print(f"linking group {group_id} <-> chat {chat_id}")
        link_group_and_chat(group_id, chat_id)
        del pending_groupids[group_id]
        linked = True
    if not linked:
        pending_chatids[chat_id] = True
    print("pending_chatids after:", pending_chatids)
@handler.add(JoinEvent)
def handle_join(event):
    group_id = event.source.group_id
    print(f"LINESDK EVENT JoinEvent group_id: {group_id}")
    print("pending_chatids before:", pending_chatids)
    linked = False
    for chat_id in list(pending_chatids):
        print(f"linking group {group_id} <-> chat {chat_id}")
        link_group_and_chat(group_id, chat_id)
        del pending_chatids[chat_id]
        linked = True
    if not linked:
        pending_groupids[group_id] = True
    print("pending_groupids after:", pending_groupids)
########################################

if __name__ == "__main__":
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', type=int, default=6100, help='port')
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()
    flask_thread = threading.Thread(target=app.run, kwargs={"debug": options.debug, "port": options.port, "use_reloader": False})
    flask_thread.start()
    try:
        bot.listen(botid=BOT_ID)
    except KeyboardInterrupt:
        print("Shutting down...")
        sys.exit(0)
