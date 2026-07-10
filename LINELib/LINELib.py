from typing import Optional, List, Dict, Any, Callable
from .AuthService import AuthService
from .ChatService import ChatService
from .util import ratelimiter, ratelimit_after
from .exceptions import LINEOAError
from .sse import SSEEvent
import os
import requests
import json
import time
import random

class LINELib:

    def __init__(self, storage: Optional[str] = None, email: Optional[str] = None, password: Optional[str] = None, rate_limit: int = 18, rate_limit_window: float = 60, rate_limit_enabled: bool = True):
        self.storage = storage or "lineoa-storage.json"
        self._storage_cache = None
        self._rate_limit = rate_limit
        self._rate_limit_window = rate_limit_window
        self._rate_limit_enabled = rate_limit_enabled
        self._auth = AuthService(cookie_store_path=self.storage)
        self._session = None
        self._user_info = None
        self._xsrf_token = None
        try:
            self._restore_session_from_cookie()
        except LINEOAError as e:
            if email and password:
                login_result = self._auth.login_with_email_and_2fa(email, password, get_2fa_code_callback=None)
                self._session = login_result.get("session")
                self._user_info = login_result.get("user_info")
                for c in self._session.cookies:
                    if c.name == "XSRF-TOKEN" and "chat.line.biz" in c.domain:
                        self._xsrf_token = c.value
                        break
            else:
                self._session = requests.Session()
        if self._session is None:
            self._session = requests.Session()
        self._chat_service = ChatService()
        self._bots = None
        self._chats = None
        self._provider = None

    def _load_storage(self):
        if getattr(self, "_storage_cache", None) is not None:
            return self._storage_cache
        if not os.path.exists(self.storage):
            self._storage_cache = {}
            return self._storage_cache
        try:
            with open(self.storage, "r", encoding="utf-8") as f:
                self._storage_cache = json.load(f)
        except Exception:
            self._storage_cache = {}
        return self._storage_cache

    def _save_storage(self, data):
        self._storage_cache = data
        with open(self.storage, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_final_send_time(self):
        data = self._load_storage()
        return data.get("FinalsendTime")

    def set_final_send_time(self, timestamp):
        data = self._load_storage()
        data["FinalsendTime"] = timestamp
        self._save_storage(data)

    def get_send_timestamps(self):
        self._clean_send_timestamps()
        data = self._load_storage()
        return data.get("SendTimestamps", [])

    def add_send_timestamp(self, timestamp: float):
        data = self._load_storage() or {}
        timestamps = data.get("SendTimestamps", [])
        timestamps.append(timestamp)
        if len(timestamps) > 20:
            timestamps = timestamps[-20:]
        data["SendTimestamps"] = timestamps
        self._save_storage(data)

    def _clean_send_timestamps(self) -> None:
        """Remove timestamps older than 60 seconds from storage."""
        data = self._load_storage() or {}
        timestamps = data.get("SendTimestamps", [])
        if not timestamps:
            return
        now = time.time()
        cleaned = [t for t in timestamps if now - t < 60]
        if len(cleaned) > 20:
            cleaned = cleaned[-20:]
        if cleaned != timestamps:
            data["SendTimestamps"] = cleaned
            self._save_storage(data)

    def check_rate_limit(self) -> Dict[str, Any]:
        """Return current rate-limit status."""
        timestamps = self.get_send_timestamps()
        limited = self._rate_limit_enabled and ratelimiter(timestamps, limit=self._rate_limit, window=self._rate_limit_window)
        return {
            "limited": limited,
            "count": len(timestamps),
            "limit": self._rate_limit,
            "window": self._rate_limit_window,
            "enabled": self._rate_limit_enabled,
            "ratelimit_after": ratelimit_after(timestamps, limit=self._rate_limit, window=self._rate_limit_window) if limited else 0,
        }

    def reset_rate_limit(self) -> None:
        """Clear all send timestamps to reset the rate-limit counter."""
        data = self._load_storage() or {}
        data["SendTimestamps"] = []
        self._save_storage(data)

    def get_streaming_api_token_and_listen_stream_events(self, bot_id: str, device_type: str = "", client_type: str = "PC", ping_secs: int = 60, last_event_id: Optional[str] = None, on_event: Optional[Callable[[Dict[str, Any]], None]] = None, stop_event: Optional[Callable[[], bool]] = None, max_stream_seconds: float = 82800) -> Optional[str]:
        """
        streamingApiToken取得→SSE接続を一連で行う
        :param bot_id: BotのID
        :param device_type: デバイスタイプ（省略可）
        :param client_type: クライアントタイプ（デフォルト: PC）
        :param ping_secs: ping間隔（デフォルト: 60秒）
        :param last_event_id: 前回受信したイベントID（省略可）
        :param on_event: イベント受信時のコールバック (dict)
        :param stop_event: 停止判定コールバック。Trueを返すとループを抜ける
        :return: 最後に受信したevent id（再接続時に使用）
        """
        try:
            token_info = self._chat_service.get_streaming_api_token(bot_id, session=self._session, xsrf_token=self._xsrf_token)
            streaming_api_token = token_info.get("streamingApiToken")
            if not isinstance(streaming_api_token, str) or not streaming_api_token:
                raise LINEOAError("streamingApiToken is missing or invalid")
            streaming_api_base_url = token_info.get("streamingApiBaseUrl", "https://chat-streaming-api.line.biz")
            streaming_api_version = token_info.get("streamingApiVersion", "v2")
            token_expired_at = token_info.get("expiredAt")
            if isinstance(token_expired_at, (int, float)):
                seconds_until_expiry = max(0.0, (float(token_expired_at) - time.time() * 1000.0) / 1000.0)
                if seconds_until_expiry > 0:
                    max_stream_seconds = min(max_stream_seconds, max(1.0, seconds_until_expiry - 60.0))
            connection_id = token_info.get("connectionId")
            if isinstance(connection_id, str) and connection_id:
                self._chat_service.streaming_state(
                    bot_id=bot_id,
                    state={"connectionId": connection_id, "idle": True},
                )
            last_event_id = last_event_id or token_info.get("lastEventId")
            for event in self._chat_service.stream_events(
                streaming_api_token,
                device_type=device_type,
                client_type=client_type,
                ping_secs=ping_secs,
                last_event_id=last_event_id,
                session=self._session,
                xsrf_token=self._xsrf_token,
                max_stream_seconds=max_stream_seconds,
                base_url=streaming_api_base_url,
                version=streaming_api_version,
            ):
                if stop_event and stop_event():
                    break
                event_id = event.get("id")
                if event_id:
                    last_event_id = event_id
                if on_event:
                    on_event(event)
        except Exception as e:
            raise
        return last_event_id

    def get_chat_members(self, bot_id=None, chat_id=None, limit: int = 100) -> Dict[str, Any]:
        """チャットメンバー一覧取得"""
        return self._chat_service.get_chat_members(
            bot_id=str(bot_id), chat_id=str(chat_id), limit=limit, session=self._session, xsrf_token=self._xsrf_token
        )

    def get_me(self) -> Dict[str, Any]:
        return self._chat_service.get_me()

    def get_bot_account(self, bot_id: str, no_filter: bool = True) -> Dict[str, Any]:
        return self._chat_service.get_bot_account(bot_id=bot_id, no_filter=no_filter)

    def get_csrf_token(self) -> Dict[str, Any]:
        return self._chat_service.get_csrf_token()

    def get_pinned_messages(self, bot_id: str, chat_id: str) -> Dict[str, Any]:
        return self._chat_service.get_pinned_messages(bot_id=bot_id, chat_id=chat_id)

    def set_typing(self, bot_id: str, chat_id: str) -> Dict[str, Any]:
        return self._chat_service.set_typing(bot_id=bot_id, chat_id=chat_id)

    def streaming_state(self, bot_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        return self._chat_service.streaming_state(bot_id=bot_id, state=state)

    def get_whitelist_domains(self) -> Dict[str, Any]:
        return self._chat_service.get_whitelist_domains()

    def get_me_settings_pc(self) -> Dict[str, Any]:
        return self._chat_service.get_me_settings_pc()

    def get_chat_mode(self, bot_id: str) -> Dict[str, Any]:
        return self._chat_service.get_chat_mode(bot_id=bot_id, session=self._session, xsrf_token=self._xsrf_token)

    def get_chat_mode_schedules(self, bot_id: str) -> Dict[str, Any]:
        return self._chat_service.get_chat_mode_schedules(bot_id=bot_id, session=self._session, xsrf_token=self._xsrf_token)

    def get_available_features(self, bot_id: str) -> Dict[str, Any]:
        return self._chat_service.get_available_features(bot_id=bot_id, session=self._session, xsrf_token=self._xsrf_token)

    def get_banner_web(self, bot_id: str) -> Dict[str, Any]:
        return self._chat_service.get_banner_web(bot_id=bot_id, session=self._session, xsrf_token=self._xsrf_token)

    def get_call_session(self, bot_id: str) -> Dict[str, Any]:
        return self._chat_service.get_call_session(bot_id=bot_id, session=self._session, xsrf_token=self._xsrf_token)

    def get_activities(self, bot_id: str, chat_id: str, limit: int = 1) -> Dict[str, Any]:
        return self._chat_service.get_activities(bot_id=bot_id, chat_id=chat_id, limit=limit, session=self._session, xsrf_token=self._xsrf_token)

    def get_notes(self, bot_id: str, chat_id: str, limit: int = 20, with_total: bool = True) -> Dict[str, Any]:
        return self._chat_service.get_notes(bot_id=bot_id, chat_id=chat_id, limit=limit, with_total=with_total, session=self._session, xsrf_token=self._xsrf_token)

    def get_authorized_users(self, bot_id: str, biz_ids: str = "__AUTO_RESPONSE") -> Dict[str, Any]:
        return self._chat_service.get_authorized_users(bot_id=bot_id, biz_ids=biz_ids, session=self._session, xsrf_token=self._xsrf_token)

    def get_use_manual_chat(self, bot_id: str, chat_id: str) -> Dict[str, Any]:
        return self._chat_service.get_use_manual_chat(bot_id=bot_id, chat_id=chat_id, session=self._session, xsrf_token=self._xsrf_token)

    def get_recent_stickers(self, bot_id: str) -> Dict[str, Any]:
        return self._chat_service.get_recent_stickers(bot_id=bot_id, session=self._session, xsrf_token=self._xsrf_token)

    def get_recent_emojis(self, bot_id: str) -> Dict[str, Any]:
        return self._chat_service.get_recent_emojis(bot_id=bot_id, session=self._session, xsrf_token=self._xsrf_token)

    def get_saved_replies(self, bot_id: str, query: str = "", exclude_username_placeholder: bool = False, sort_key: str = "CREATED_AT", page_size: int = 25, page: int = 1) -> Dict[str, Any]:
        return self._chat_service.get_saved_replies(bot_id=bot_id, query=query, exclude_username_placeholder=exclude_username_placeholder, sort_key=sort_key, page_size=page_size, page=page, session=self._session, xsrf_token=self._xsrf_token)

    def get_clock_now(self) -> Dict[str, Any]:
        return self._chat_service.get_clock_now(session=self._session, xsrf_token=self._xsrf_token)

    def get_holiday(self, country: str = "JP") -> Dict[str, Any]:
        return self._chat_service.get_holiday(country=country, session=self._session, xsrf_token=self._xsrf_token)

    def get_plugins(self, bot_id: str) -> Dict[str, Any]:
        return self._chat_service.get_plugins(bot_id=bot_id, session=self._session, xsrf_token=self._xsrf_token)

    def get_image_preview(self, bot_id: str, content_hash: str) -> bytes:
        return self._chat_service.get_content_preview(bot_id=bot_id, content_hash=content_hash, session=self._session, xsrf_token=self._xsrf_token)

    def save_image_preview(self, bot_id: str, content_hash: str, file_path: str) -> str:
        data = self.get_image_preview(bot_id=bot_id, content_hash=content_hash)
        with open(file_path, "wb") as f:
            f.write(data)
        return file_path

    def normalize_message_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        sse_event = SSEEvent(id=event.get("id"), event=event.get("type"), data=json.dumps(event.get("payload", {}), ensure_ascii=False))
        normalized = sse_event.normalized_message()
        if normalized is None:
            return {
                "kind": "unknown",
                "raw_event": event,
            }
        return normalized

    def save_message_media(self, event: Dict[str, Any], file_path: str) -> str:
        normalized = self.normalize_message_event(event)
        message_type = normalized.get("message_type")
        bot_id = normalized.get("bot_id")
        target_path = file_path
        if not os.path.splitext(target_path)[1]:
            extension = normalized.get("extension")
            if message_type == "link":
                extension = "json"
            elif message_type == "sticker":
                extension = "png"
            if extension:
                target_path = f"{target_path}.{extension}"

        if message_type == "link":
            payload = {
                "message_id": normalized.get("message_id"),
                "bot_id": bot_id,
                "chat_id": normalized.get("chat_id"),
                "title": normalized.get("title"),
                "url": normalized.get("url"),
                "text": normalized.get("text"),
                "timestamp": normalized.get("timestamp"),
                "raw": normalized.get("raw"),
            }
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return target_path

        if message_type == "sticker":
            sticker_id = normalized.get("sticker_id")
            if not sticker_id:
                raise LINEOAError("message does not contain sticker_id")
            return self._chat_service.save_sticker_image(
                sticker_id=str(sticker_id),
                file_path=target_path,
                session=self._session,
            )

        content_hash = normalized.get("content_hash")
        if not bot_id or not content_hash:
            raise LINEOAError("message does not contain downloadable media")
        return self._chat_service.save_content_preview(
            bot_id=bot_id,
            content_hash=content_hash,
            file_path=target_path,
            session=self._session,
            xsrf_token=self._xsrf_token,
        )

    def send_file(self, chat_id: str, file_path: str, bot_id: Optional[str] = None) -> Dict[str, Any]:
        """
        指定チャットにファイルを送信
        :param chat_id: チャットID
        :param file_path: ファイルパス
        :param bot_id: 利用するbotId（省略時は先頭bot）
        """
        if bot_id is None:
            bot_id = next(iter(self.bots.ids.values()), None)
        if not bot_id:
            raise LINEOAError("No bot found")
        timestamps = self.get_send_timestamps()
        if self._rate_limit_enabled and ratelimiter(timestamps, limit=self._rate_limit, window=self._rate_limit_window):
            return {"ratelimit": True, "ratelimit_after": ratelimit_after(timestamps, limit=self._rate_limit, window=self._rate_limit_window)}
        self.add_send_timestamp(time.time())
        return self._chat_service.send_file(
            bot_id, chat_id, file_path, session=self._session, xsrf_token=self._xsrf_token
        )
    
    def listen_stream_events(self, streaming_api_token: str, device_type: str = "", client_type: str = "PC", ping_secs: int = 60, last_event_id: Optional[str] = None, on_event: Optional[Callable[[Dict[str, Any]], None]] = None, max_stream_seconds: float = 82800, base_url: str = "https://chat-streaming-api.line.biz", version: str = "v2") -> None:
        """
        chat-streaming-api.line.biz SSEイベント受信
        :param streaming_api_token: SSE用トークン
        :param device_type: デバイスタイプ（省略可）
        :param client_type: クライアントタイプ（デフォルト: PC）
        :param ping_secs: ping間隔（デフォルト: 60秒）
        :param last_event_id: 前回受信したイベントID（省略可）
        :param on_event: イベント受信時のコールバック (dict)
        """
        for event in self._chat_service.stream_events(
            streaming_api_token,
            device_type=device_type,
            client_type=client_type,
            ping_secs=ping_secs,
            last_event_id=last_event_id,
            session=self._session,
            xsrf_token=self._xsrf_token,
            max_stream_seconds=max_stream_seconds,
            base_url=base_url,
            version=version,
        ):
            if on_event:
                on_event(event)

    def get_chat_messages(self, bot_id: str, chat_id: str, limit: int = 50, before: Optional[str] = None, after: Optional[str] = None) -> Dict[str, Any]:
        """
        指定チャットのメッセージ一覧を取得 (公式Webクライアント完全再現)
        :param bot_id: BotのID
        :param chat_id: チャットID
        :param limit: 取得件数
        :param before: これより前のメッセージID（任意）
        :param after: これより後のメッセージID（任意）
        """
        return self._chat_service.get_chat_messages(
            bot_id, chat_id,
            session=self._session,
            xsrf_token=self._xsrf_token,
            limit=limit,
            before=before,
            after=after
        )

    def listen_messages(self, bot_id: str, chat_id: str, on_message: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        """
        指定チャットのメッセージをリアルタイムで監視 (SSE)
        :param bot_id: BotのID
        :param chat_id: チャットID
        :param on_message: 新着メッセージ受信時のコールバック (dict)
        """
        return self._chat_service.listen_messages(bot_id, chat_id, on_message)

    def get_bots(self):
        if self._bots is None:
            bots = self._chat_service.get_bot_accounts(session=self._session, xsrf_token=self._xsrf_token)
            # bots: list of dicts with 'botId' and 'name'
            self._bots = BotsInfo(bots.get("list", []))
        return self._bots
    
    def get_chats(self, bot_id: str, limit: int) -> Dict[str, Any]:
        """
        指定Botのチャット一覧を取得
        :param bot_id: BotのID
        """
        return self._chat_service.get_chats(
            bot_id, session=self._session, xsrf_token=self._xsrf_token, limit=limit
        )

    def send_message(self, user_id: str, context: str, bot_id: Optional[str] = None, quoteToken: Optional[str] = None) -> Dict[str, Any]:
        """
        指定ユーザーにテキストメッセージを送信
        :param user_id: チャットID（ユーザーID）
        :param context: 送信するテキスト
        :param bot_id: 利用するbotId（省略時は先頭bot）
        :param quoteToken: リプライ用(省略時は普通のメッセージ)
        """
        if bot_id is None:
            bot_id = next(iter(self.bots.ids.values()), None)
        if not bot_id:
            raise LINEOAError("No bot found")
        timestamps = self.get_send_timestamps()
        if self._rate_limit_enabled and ratelimiter(timestamps, limit=self._rate_limit, window=self._rate_limit_window):
            return {"ratelimit": True, "ratelimit_after": ratelimit_after(timestamps, limit=self._rate_limit, window=self._rate_limit_window)}
        now = int(time.time() * 1000)
        send_id = f"{user_id}_{now}_{random.randint(1000000,9999999)}"
        payload = {
            "id": "",
            "type": "textV2",
            "text": context,
            "sendId": send_id
        }
        if quoteToken:
            payload["quoteToken"] = quoteToken
        self.set_final_send_time(int(time.time()))
        self.add_send_timestamp(time.time())
        return self._chat_service.send_message(
            bot_id, user_id, payload, session=self._session, xsrf_token=self._xsrf_token
        )
    async def async_send_message(self, user_id: str, context: str, bot_id: Optional[str] = None, quoteToken: Optional[str] = None) -> Dict[str, Any]:
        """Async wrapper for sending a text message."""
        if bot_id is None:
            bot_id = next(iter(self.bots.ids.values()), None)
        if not bot_id:
            raise LINEOAError("No bot found")
        now = int(time.time() * 1000)
        send_id = f"{user_id}_{now}_{random.randint(1000000,9999999)}"
        payload = {"id": "", "type": "textV2", "text": context, "sendId": send_id}
        if quoteToken:
            payload["quoteToken"] = quoteToken
        cookies = {}
        if hasattr(self, '_session') and isinstance(self._session, requests.Session):
            for c in self._session.cookies:
                cookies[c.name] = c.value
        return await self._chat_service.async_send_message(bot_id, user_id, payload, cookies=cookies, xsrf_token=self._xsrf_token)
    
    def send_mention(self, bot_id: str, chat_id: str, mentionee_id: str) -> Dict[str, Any]:
        """
        メンション送信（レートリミット判定あり）
        """
        timestamps = self.get_send_timestamps()
        if self._rate_limit_enabled and ratelimiter(timestamps, limit=self._rate_limit, window=self._rate_limit_window):
            return {"ratelimit": True, "ratelimit_after": ratelimit_after(timestamps, limit=self._rate_limit, window=self._rate_limit_window)}
        self.add_send_timestamp(time.time())
        return self._chat_service.send_mention(bot_id, chat_id, mentionee_id, session=self._session, xsrf_token=self._xsrf_token)

    def sendMessage(self, user_id: str, text: str, bot_id: Optional[str] = None, quoteToken: Optional[str] = None):
        return self.send_message(user_id, text, bot_id=bot_id, quoteToken=quoteToken)

    def sendFile(self, chat_id: str, file_path: str, bot_id: Optional[str] = None):
        return self.send_file(chat_id, file_path, bot_id=bot_id)

    def sendMention(self, bot_id: str, chat_id: str, mentionee_id: str):
        return self.send_mention(bot_id, chat_id, mentionee_id)

    def getMessages(self, bot_id: str, chat_id: str, limit: int = 50, before: Optional[str] = None, after: Optional[str] = None) -> Dict[str, Any]:
        return self.get_chat_messages(bot_id=bot_id, chat_id=chat_id, limit=limit, before=before, after=after)

    def getChats(self, bot_id: str, limit: int = 25) -> Dict[str, Any]:
        return self.get_chats(bot_id=bot_id, limit=limit)

    def getMembers(self, bot_id: str, chat_id: str, limit: int = 100) -> Dict[str, Any]:
        return self.get_chat_members(bot_id=bot_id, chat_id=chat_id, limit=limit)

    def _restore_session_from_cookie(self) -> None:
        if not os.path.exists(self.storage):
            raise LINEOAError("cookie storage does not exist. Please save logged-in cookies.")
        if os.path.getsize(self.storage) == 0:
            raise LINEOAError("cookie storage is empty. Please save logged-in cookies.")
        with open(self.storage, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "cookies" not in data:
            raise LINEOAError("cookie storage is invalid")
        session = requests.Session()
        for c in data["cookies"]:
            session.cookies.set(c["name"], c["value"], domain=c.get("domain"))
        self._session = session
        self._user_info = {"email": data.get("email"), "user_name": data.get("user_name")}
        for c in session.cookies:
            if c.name == "XSRF-TOKEN" and "chat.line.biz" in c.domain:
                self._xsrf_token = c.value
                break

    async def async_send_file(self, chat_id: str, file_path: str, bot_id: Optional[str] = None) -> Dict[str, Any]:
        """Async wrapper for sending a file."""
        if bot_id is None:
            bot_id = next(iter(self.bots.ids.values()), None)
        if not bot_id:
            raise LINEOAError("No bot found")
        cookies = {}
        if hasattr(self, '_session') and isinstance(self._session, requests.Session):
            for c in self._session.cookies:
                cookies[c.name] = c.value
        return await self._chat_service.async_send_file(bot_id, chat_id, file_path, cookies=cookies, xsrf_token=self._xsrf_token)

    async def async_send_mention(self, bot_id: str, chat_id: str, mentionee_id: str) -> Dict[str, Any]:
        """Async wrapper for sending a mention."""
        mention_text = f"@{mentionee_id} "
        payload = {
            "type": "text",
            "text": mention_text,
            "mentions": [{"userId": mentionee_id, "offset": 0, "length": len(mention_text)}]
        }
        cookies = {}
        if hasattr(self, '_session') and isinstance(self._session, requests.Session):
            for c in self._session.cookies:
                cookies[c.name] = c.value
        return await self._chat_service.async_send_message(bot_id, chat_id, payload, cookies=cookies, xsrf_token=self._xsrf_token)

    async def async_get_chat_messages(self, bot_id: str, chat_id: str, limit: int = 50, before: Optional[str] = None, after: Optional[str] = None) -> Dict[str, Any]:
        """Async wrapper for fetching chat messages."""
        cookies = {}
        if hasattr(self, '_session') and isinstance(self._session, requests.Session):
            for c in self._session.cookies:
                cookies[c.name] = c.value
        return await self._chat_service.async_get_chat_messages(bot_id, chat_id, cookies=cookies, xsrf_token=self._xsrf_token, limit=limit, before=before, after=after)

    @property
    def bots(self):
        if self._bots is None:
            bots = self._chat_service.get_bot_accounts(session=self._session, xsrf_token=self._xsrf_token)
            # bots: list of dicts with 'botId' and 'name'
            self._bots = BotsInfo(bots.get("list", []))
        return self._bots
    @property
    def chats(self):
        if self._chats is None:
            bot_id = next(iter(self.bots.ids.values()), None)
            if not bot_id:
                raise LINEOAError("No bot found")
            try:
                chats = self._chat_service.get_chats(bot_id, session=self._session, xsrf_token=self._xsrf_token)
                self._chats = ChatsInfo(chats.get("list", []))
            except Exception as e:
                raise LINEOAError(f"チャット一覧取得失敗: {e}")
        return self._chats

    @property
    def provider(self):
        if self._provider is None:
            try:
                url = "https://chat.line.biz/api/v1/providers"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                }
                if self._session is None:
                    self._session = requests.Session()
                resp = self._session.get(url, headers=headers)
                if resp.ok:
                    self._provider = resp.json()
                else:
                    self._provider = []
                    raise LINEOAError(f"プロバイダー取得失敗: {resp.status_code} {resp.text}")
            except Exception as e:
                self._provider = []
                raise LINEOAError(f"プロバイダー取得例外: {e}")
        return self._provider

class BotsInfo:
    def __init__(self, bots_list: List[Dict[str, Any]]):
        self._bots = bots_list
    @property
    def ids(self) -> Dict[str, str]:
        result = {}
        for b in self._bots:
            u_id = b.get("botId")
            at_id = b.get("basicSearchId")
            name = b.get("name", "")
            if u_id:
                key = at_id if at_id else name
                result[key] = u_id
        return result
    def __repr__(self) -> str:
        entries = []
        for b in self._bots:
            name = b.get("name", "unknown")
            bot_id = b.get("botId", "")
            search_id = b.get("basicSearchId", "")
            entries.append(f"  {name} : {bot_id} ({search_id})")
        return f"BotsInfo({len(self._bots)} bots)\n" + "\n".join(entries)

class ChatsInfo:
    def __init__(self, chats_list: List[Dict[str, Any]]):
        self._chats = chats_list
        self.group = ChatTypeIds(self._chats, "GROUP")
        self.user = ChatTypeIds(self._chats, "USER")
    def __repr__(self) -> str:
        lines = []
        for c in self._chats:
            profile = c.get("profile", {})
            chat_id = c.get("chatId", "unknown")
            name = profile.get("name", chat_id)
            chat_type = c.get("chatType", "")
            lines.append(f"  {name} : {chat_id}  [{chat_type}]")
        return f"ChatsInfo({len(self._chats)} chats)\n" + "\n".join(lines)

class ChatTypeIds:
    def __init__(self, chats: List[Dict[str, Any]], chat_type: str):
        self._type = chat_type
        self._chats = [c for c in chats if c.get("chatType") == chat_type]
        self._ids = [c["chatId"] for c in self._chats]
    @property
    def ids(self) -> List[str]:
        return self._ids
    def __repr__(self) -> str:
        lines = []
        for c in self._chats:
            profile = c.get("profile", {})
            chat_id = c.get("chatId", "unknown")
            name = profile.get("name", chat_id)
            lines.append(f"  {name} : {chat_id}")
        return f"ChatTypeIds({self._type}, {len(self._ids)} chats)\n" + "\n".join(lines)
