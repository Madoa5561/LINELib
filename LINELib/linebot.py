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
        max_stream_seconds=82800,
        get_2fa_code_callback=None,
        interactive_login=False,
        browser_channel="chrome",
        interactive_timeout=300,
    ):
        self.cookie_path = cookie_path
        self.listen_config = ListenConfig(
            ping_secs=ping_secs,
            device_type=device_type,
            client_type=client_type,
            reconnect_interval=reconnect_interval,
            max_reconnects=max_reconnects,
            max_stream_seconds=max_stream_seconds,
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
        self._last_event_ids = {}
        self._lib = LINELib(
            storage=self.cookie_path,
            email=email,
            password=password,
            rate_limit=rate_limit,
            rate_limit_window=rate_limit_window,
            rate_limit_enabled=rate_limit_enabled,
            get_2fa_code_callback=get_2fa_code_callback,
            interactive_login=interactive_login,
            browser_channel=browser_channel,
            interactive_timeout=interactive_timeout,
        )
        self._session = self._lib._session
        self._xsrf_token = self._lib._xsrf_token
        self._bot_ids = None
        if hasattr(self._lib, "bots") and hasattr(self._lib.bots, "ids"):
            self._bot_ids = list(self._lib.bots.ids.values())
        if self._bot_ids:
            lineoa_logger.login("Login success (bot account loaded)")
        else:
            lineoa_logger.info("Client initialized; authentication has not been verified")

    def sendMessage(self, bot_id=None, chat_id=None, text=None, quoteToken=None):
        """Send a text message to the given chat."""
        if chat_id is None:
            raise ValueError("chat_id is required")
        if text is None:
            raise ValueError("text is required")
        return self._lib.sendMessage(user_id=str(chat_id), text=str(text), bot_id=bot_id, quoteToken=quoteToken)

    def sendFile(self, bot_id=None, chat_id=None, file_path=None):
        """Send a file to the given chat."""
        if chat_id is None:
            raise ValueError("chat_id is required")
        if file_path is None:
            raise ValueError("file_path is required")
        return self._lib.sendFile(chat_id=str(chat_id), file_path=str(file_path), bot_id=bot_id)

    def getRateLimitStatus(self):
        """Return local send rate-limit status."""
        return self._lib.check_rate_limit()

    def resetRateLimit(self):
        """Clear local send rate-limit timestamps."""
        return self._lib.reset_rate_limit()

    def getChatMessages(self, bot_id=None, chat_id=None, limit=50, before=None, after=None):
        """Get messages for a chat."""
        if chat_id is None:
            raise ValueError("chat_id is required")
        return self._lib.getMessages(bot_id=self._resolve_bot_id(bot_id), chat_id=str(chat_id), limit=limit, before=before, after=after)

    def getMembers(self, bot_id=None, chat_id=None, limit=100):
        """Get members for a chat."""
        if chat_id is None:
            raise ValueError("chat_id is required")
        return self._lib.getMembers(bot_id=self._resolve_bot_id(bot_id), chat_id=str(chat_id), limit=limit)

    def getBots(self):
        """Get available bot accounts."""
        return self._lib.get_bots()

    def getChats(self, bot_id=None, limit=100):
        """Get chats for a bot."""
        return self._lib.getChats(bot_id=self._resolve_bot_id(bot_id), limit=limit)

    def normalize_message_event(self, event):
        """Normalize a received SSE event into a stable message shape."""
        return self._lib.normalize_message_event(event)

    def save_message_media(self, event, file_path):
        """Save media or link metadata from a received event."""
        return self._lib.save_message_media(event, file_path)

    def get_image_preview(self, bot_id, content_hash):
        return self._lib.get_image_preview(bot_id, content_hash)

    def save_image_preview(self, bot_id, content_hash, file_path):
        return self._lib.save_image_preview(bot_id, content_hash, file_path)

    def save_sticker_image(self, sticker_id, file_path):
        return self._lib.save_sticker_image(sticker_id, file_path)

    def get_me(self):
        return self._lib.get_me()

    def get_bot_account(self, bot_id, no_filter=True):
        return self._lib.get_bot_account(bot_id, no_filter=no_filter)

    def get_csrf_token(self):
        return self._lib.get_csrf_token()

    def get_pinned_messages(self, bot_id, chat_id):
        return self._lib.get_pinned_messages(bot_id, chat_id)

    def set_typing(self, bot_id, chat_id):
        return self._lib.set_typing(bot_id, chat_id)

    def get_whitelist_domains(self):
        return self._lib.get_whitelist_domains()

    def get_me_settings_pc(self):
        return self._lib.get_me_settings_pc()

    def get_chat_mode(self, bot_id):
        return self._lib.get_chat_mode(bot_id)

    def get_chat_mode_schedules(self, bot_id):
        return self._lib.get_chat_mode_schedules(bot_id)

    def get_available_features(self, bot_id):
        return self._lib.get_available_features(bot_id)

    def get_banner_web(self, bot_id):
        return self._lib.get_banner_web(bot_id)

    def get_call_session(self, bot_id):
        return self._lib.get_call_session(bot_id)

    def get_activities(self, bot_id, chat_id, limit=1):
        return self._lib.get_activities(bot_id, chat_id, limit=limit)

    def get_notes(self, bot_id, chat_id, limit=20, with_total=True):
        return self._lib.get_notes(bot_id, chat_id, limit=limit, with_total=with_total)

    def get_authorized_users(self, bot_id, biz_ids="__AUTO_RESPONSE"):
        return self._lib.get_authorized_users(bot_id, biz_ids=biz_ids)

    def get_use_manual_chat(self, bot_id, chat_id):
        return self._lib.get_use_manual_chat(bot_id, chat_id)

    def get_recent_stickers(self, bot_id):
        return self._lib.get_recent_stickers(bot_id)

    def get_recent_emojis(self, bot_id):
        return self._lib.get_recent_emojis(bot_id)

    def get_saved_replies(self, bot_id, query="", exclude_username_placeholder=False, sort_key="CREATED_AT", page_size=25, page=1):
        return self._lib.get_saved_replies(
            bot_id,
            query=query,
            exclude_username_placeholder=exclude_username_placeholder,
            sort_key=sort_key,
            page_size=page_size,
            page=page,
        )

    def get_clock_now(self):
        return self._lib.get_clock_now()

    def get_holiday(self, country="JP"):
        return self._lib.get_holiday(country)

    def get_plugins(self, bot_id):
        return self._lib.get_plugins(bot_id)

    def create_and_send_flex(self, **kwargs):
        return self._lib.create_and_send_flex(**kwargs)

    def event(self, func):
        self.handlers[func.__name__] = func
        return func

    def dispatch(self, event_type, event):
        payload = event.get("payload")
        if not isinstance(payload, dict):
            payload = {}
            event = dict(event)
            event["payload"] = payload
        subevent = payload.get("subEvent")
        inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        payload_type = inner.get("type")
        normalized = self._lib.normalize_message_event(event)
        message_type = normalized.get("message_type")
        if message_type:
            event = dict(event)
            event["normalized"] = normalized

        media_types = {"image", "video", "file", "audio", "sticker", "link"}
        handler = None
        if event_type in {"init", "ping"}:
            handler = self.handlers.get(f"on_{event_type}")
        if not handler and message_type:
            handler = self.handlers.get(f"on_{message_type}")
        if not handler and message_type in media_types:
            handler = self.handlers.get("on_media")
        if not handler and (subevent == "message" or payload_type == "message" or message_type):
            handler = self.handlers.get("on_message")
        if not handler and subevent:
            handler = self.handlers.get(f"on_{subevent}")
        if not handler and event_type:
            handler = self.handlers.get(f"on_{event_type}")
        if not handler:
            handler = self.handlers.get("on_unknown")
        if handler:
            try:
                handler(event)
            except Exception as e:
                lineoa_logger.exception(f"handler error ({handler.__name__}): {e}")

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
            event_id = event.get("id")
            if event_id:
                self._last_event_ids[bot_id] = event_id
            event_type = event.get("type")
            self.dispatch(event_type, event)

        reconnects = 0
        try:
            while not self._stop_event.is_set():
                try:
                    last_event_id = self._lib.get_streaming_api_token_and_listen_stream_events(
                        bot_id=bot_id,
                        device_type=self.device_type,
                        client_type=self.client_type,
                        ping_secs=self.ping_secs,
                        last_event_id=self._last_event_ids.get(bot_id),
                        on_event=_on_event,
                        stop_event=self._stop_event.is_set,
                        max_stream_seconds=self.listen_config.max_stream_seconds,
                    )
                    if last_event_id:
                        self._last_event_ids[bot_id] = last_event_id
                    if self._stop_event.is_set():
                        break
                    reconnects = 0
                except Exception as e:
                    if self._stop_event.is_set():
                        break
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
        if self._listen_thread and self._listen_thread.is_alive():
            raise RuntimeError("Polling is already running")
        botid = self._resolve_bot_id(botid)
        self.running = True
        self._stop_event.clear()
        self._listen_thread = threading.Thread(target=self._polling_loop, args=(botid,), daemon=True)
        self._listen_thread.start()
        if not block:
            return self._listen_thread
        listen_thread = self._listen_thread
        try:
            while self.running:
                listen_thread.join(1)
        except KeyboardInterrupt:
            self.stop()
            print("Bot stopped.")

    def stop(self):
        self._stop_event.set()
        try:
            self._lib._close_stream()
        except Exception as error:
            lineoa_logger.error(f"Failed to close polling stream: {error}")
        if (
            self._listen_thread
            and self._listen_thread.is_alive()
            and threading.current_thread() is not self._listen_thread
        ):
            self._listen_thread.join(timeout=5)
        if (
            self._listen_thread is None
            or not self._listen_thread.is_alive()
            or threading.current_thread() is self._listen_thread
        ):
            self.running = False
