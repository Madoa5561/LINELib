import threading
from LINELib.LINELib import LINELib
from LINELib.logger import lineoa_logger

class LineBot:
    def __init__(self, cookie_path="lineoa-storage.json", ping_secs=60, device_type="", client_type="PC", email=None, password=None):
        self.cookie_path = cookie_path
        self.ping_secs = ping_secs
        self.device_type = device_type
        self.client_type = client_type
        self.handlers = {}
        self.running = False
        self._lib = LINELib(storage=self.cookie_path, email=email, password=password)
        self._session = self._lib._session
        self._xsrf_token = self._lib._xsrf_token
        self._bot_ids = None
        if hasattr(self._lib, 'bots') and hasattr(self._lib.bots, 'ids'):
            self._bot_ids = list(self._lib.bots.ids.values())
        lineoa_logger.login("Login success (cookie loaded)")

    def sendMessage(self, bot_id=None, chat_id=None, text=None, quoteToken=None):
        """テキストメッセージ送信"""
        return self._lib.sendMessage(str(chat_id), str(text), bot_id=bot_id, quoteToken=quoteToken)

    def sendFile(self, bot_id=None, chat_id=None, file_path=None):
        """ファイル送信"""
        return self._lib.sendFile(str(chat_id), str(file_path), bot_id=bot_id)

    def getChatMessages(self, bot_id=None, chat_id=None, limit=50, before=None, after=None):
        """チャット履歴取得"""
        return self._lib.getMessages(bot_id=str(bot_id), chat_id=str(chat_id), limit=limit, before=before, after=after)

    def getMembers(self, bot_id=None, chat_id=None, limit=100):
        """チャットメンバー取得"""
        return self._lib.getMembers(bot_id=str(bot_id), chat_id=str(chat_id), limit=limit)
    
    def getBots(self):
        """botアカウントの一覧取得"""
        return self._lib.get_bots()
    
    def getChats(self, bot_id=None, limit=100):
        """チャット一覧取得"""
        return self._lib.getChats(bot_id=str(bot_id), limit=limit)
    
    def event(self, func):
        self.handlers[func.__name__] = func
        return func

    def dispatch(self, event_type, event):
        payload = event.get('payload')
        if not isinstance(payload, dict):
            payload = {}
            event = dict(event)
            event['payload'] = payload
        subevent = payload.get('subEvent')
        payload_type = None
        if isinstance(payload.get('payload'), dict):
            payload_type = payload['payload'].get('type')

        handler = None
        if subevent:
            handler = self.handlers.get(f'on_{subevent}')
        if not handler and payload_type:
            handler = self.handlers.get(f'on_{payload_type}')
        if not handler and subevent == 'message' and payload_type == 'message':
            handler = self.handlers.get('on_message')
        if not handler:
            handler = self.handlers.get('on_unknown')
        if handler:
            handler(event)

    def _polling_loop(self, bot_id):
        lineoa_logger.info(f"Polling start (botid={bot_id})")
        def _on_event(event):
            event_type = event.get('type')
            self.dispatch(event_type, event)
        self._lib.get_streaming_api_token_and_listen_stream_events(
            bot_id=bot_id,
            device_type=self.device_type,
            client_type=self.client_type,
            ping_secs=self.ping_secs,
            on_event=_on_event
        )

    def listen(self, botid=None):
        if botid is None:
            if self._bot_ids and len(self._bot_ids) > 0:
                botid = self._bot_ids[0]
            else:
                raise RuntimeError("No bot_id found. Please check your cookie file.")
        self.running = True
        thread = threading.Thread(target=self._polling_loop, args=(botid,), daemon=True)
        thread.start()
        try:
            while self.running:
                thread.join(1)
        except KeyboardInterrupt:
            self.running = False
            print('Bot stopped.')





