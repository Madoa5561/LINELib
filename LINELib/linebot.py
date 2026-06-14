import threading
from LINELib.LINELib import LINELib
from LINELib.config import ListenConfig
from LINELib.logger import lineoa_logger

class LineBot:
    def __init__(
        self,
        cookie_path="lineoa-storage.json",
        ping_secs=60,
        device_type="",
        client_type="PC",
        email=None,
        password=None,
        rate_limit=18,
        rate_limit_window=60,
        rate_limit_enabled=True,
        reconnect_interval=5,
        max_reconnects=None,
    ):
        self.cookie_path = cookie_path
        self.listen_config = ListenConfig(
            ping_secs=ping_secs,
            device_type=device_type,
            client_type=client_type,
            reconnect_interval=reconnect_interval,
            max_reconnects=max_reconnects,
        )
        self.ping_secs = self.listen_config.ping_secs
        self.device_type = self.listen_config.device_type
        self.client_type = self.listen_config.client_type
        self.handlers = {}
        self.running = False
        self.reconnect_interval = self.listen_config.reconnect_interval
        self.max_reconnects = self.listen_config.max_reconnects
        self._stop_event = threading.Event()
        self._listen_thread = None
        self._last_event_id = None
        self._lib = LINELib(
            storage=self.cookie_path,
            email=email,
            password=password,
            rate_limit=rate_limit,
            rate_limit_window=rate_limit_window,
            rate_limit_enabled=rate_limit_enabled,
        )
        self._session = self._lib._session
        self._xsrf_token = self._lib._xsrf_token
        self._bot_ids = None
        try:
            if hasattr(self._lib, 'bots') and hasattr(self._lib.bots, 'ids'):
                self._bot_ids = list(self._lib.bots.ids.values())
        except Exception as e:
            lineoa_logger.error(f"Failed to preload bot ids: {e}")
        lineoa_logger.login("Login success (cookie loaded)")

    def sendMessage(self, bot_id=None, chat_id=None, text=None, quoteToken=None):
        """テキストメッセージ送信"""
        return self._lib.sendMessage(str(chat_id), str(text), bot_id=bot_id, quoteToken=quoteToken)

    def sendFile(self, bot_id=None, chat_id=None, file_path=None):
        """ファイル送信"""
        return self._lib.sendFile(str(chat_id), str(file_path), bot_id=bot_id)

    def getRateLimitStatus(self):
        """Return local send rate-limit status."""
        return self._lib.check_rate_limit()

    def resetRateLimit(self):
        """Clear local send rate-limit timestamps."""
        return self._lib.reset_rate_limit()

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
            try:
                handler(event)
            except Exception as e:
                lineoa_logger.error(f"handler error ({handler.__name__}): {e}")

    def _resolve_bot_id(self, botid=None):
        if botid:
            return botid
        if self._bot_ids:
            return self._bot_ids[0]
        bots = self._lib.get_bots()
        self._bot_ids = list(bots.ids.values())
        if self._bot_ids:
            return self._bot_ids[0]
        raise RuntimeError("No bot_id found. Please check your cookie file.")

    def _polling_loop(self, bot_id):
        lineoa_logger.info(f"Polling start (botid={bot_id})")
        def _on_event(event):
            event_type = event.get('type')
            self.dispatch(event_type, event)
        reconnects = 0
        try:
            while not self._stop_event.is_set():
                try:
                    self._last_event_id = self._lib.get_streaming_api_token_and_listen_stream_events(
                        bot_id=bot_id,
                        device_type=self.device_type,
                        client_type=self.client_type,
                        ping_secs=self.ping_secs,
                        last_event_id=self._last_event_id,
                        on_event=_on_event,
                        stop_event=self._stop_event.is_set,
                    )
                    if self._stop_event.is_set():
                        break
                    reconnects = 0
                except Exception as e:
                    reconnects += 1
                    lineoa_logger.error(f"Polling connection error: {e}")
                    if self.max_reconnects is not None and reconnects > self.max_reconnects:
                        lineoa_logger.error("Polling stopped: max reconnects exceeded")
                        break
                if not self._stop_event.wait(self.reconnect_interval):
                    lineoa_logger.info("Polling reconnecting")
        finally:
            self.running = False

    def listen(self, botid=None, block=True):
        botid = self._resolve_bot_id(botid)
        self.running = True
        self._stop_event.clear()
        self._listen_thread = threading.Thread(target=self._polling_loop, args=(botid,), daemon=True)
        self._listen_thread.start()
        if not block:
            return self._listen_thread
        try:
            while self.running:
                self._listen_thread.join(1)
        except KeyboardInterrupt:
            self.stop()
            print('Bot stopped.')

    def stop(self):
        self.running = False
        self._stop_event.set()
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=5)