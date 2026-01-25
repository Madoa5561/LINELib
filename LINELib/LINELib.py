from typing import Optional, List, Dict, Any, Callable
from .AuthService import AuthService
from .chatService import ChatService
from .exceptions import LINEOAError
import os
import requests
import json
import time
import random

class LINELib:
    def get_streaming_api_token_and_listen_stream_events(self, bot_id: str, device_type: str = "", client_type: str = "PC", ping_secs: int = 60, last_event_id: Optional[str] = None, on_event: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        """
        streamingApiToken取得→SSE接続を一連で行う
        :param bot_id: BotのID
        :param device_type: デバイスタイプ（省略可）
        :param client_type: クライアントタイプ（デフォルト: PC）
        :param ping_secs: ping間隔（デフォルト: 60秒）
        :param last_event_id: 前回受信したイベントID（省略可）
        :param on_event: イベント受信時のコールバック (dict)
        """
        try:
            token_info = self._chat_service.get_streaming_api_token(bot_id, session=self._session, xsrf_token=self._xsrf_token)
            streaming_api_token = token_info.get("streamingApiToken")
            if not isinstance(streaming_api_token, str) or not streaming_api_token:
                raise LINEOAError("streamingApiToken is missing or invalid")
            last_event_id = last_event_id or token_info.get("lastEventId")
            for event in self._chat_service.stream_events(
                streaming_api_token,
                device_type=device_type,
                client_type=client_type,
                ping_secs=ping_secs,
                last_event_id=last_event_id,
                session=self._session,
                xsrf_token=self._xsrf_token
            ):
                if on_event:
                    on_event(event)
        except Exception as e:
            print("[EXCEPTION in get_streaming_api_token_and_listen_stream_events]", e)

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
        return self._chat_service.send_file(
            bot_id, chat_id, file_path, session=self._session, xsrf_token=self._xsrf_token
        )
    
    def listen_stream_events(self, streaming_api_token: str, device_type: str = "", client_type: str = "PC", ping_secs: int = 60, last_event_id: Optional[str] = None, on_event: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
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
            xsrf_token=self._xsrf_token
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
        :return: dict (list: メッセージ情報配列)
        """
        return self._chat_service.get_chat_messages(
            bot_id, chat_id,
            session=self._session,
            xsrf_token=self._xsrf_token,
            limit=limit,
            before=before,
            after=after
        )

    def __init__(self, storage: Optional[str] = None):
        self.storage = storage or "lineoa-storage.json"
        self._auth = AuthService(cookie_store_path=self.storage)
        self._session = None
        self._user_info = None
        self._xsrf_token = None
        try:
            self._restore_session_from_cookie()
        except LINEOAError as e:
            login_result = self._auth.login_with_email_and_2fa(None, None, get_2fa_code_callback=None)
            self._session = login_result.get("session")
            self._user_info = login_result.get("user_info")
            for c in self._session.cookies:
                if c.name == "XSRF-TOKEN" and "chat.line.biz" in c.domain:
                    self._xsrf_token = c.value
                    break
        if self._session is None:
            self._session = requests.Session()
        self._chat_service = ChatService("")
        self._bots = None
        self._chats = None
        self._provider = None

    def listen_messages(self, bot_id: str, chat_id: str, on_message: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        """
        指定チャットのメッセージをリアルタイムで監視 (SSE)
        :param bot_id: BotのID
        :param chat_id: チャットID
        :param on_message: 新着メッセージ受信時のコールバック (dict)
        """
        return self._chat_service.listen_messages(bot_id, chat_id, on_message)

    def send_message(self, user_id: str, context: str, bot_id: Optional[str] = None) -> Dict[str, Any]:
        """
        指定ユーザーにテキストメッセージを送信
        :param user_id: チャットID（ユーザーID）
        :param context: 送信するテキスト
        :param bot_id: 利用するbotId（省略時は先頭bot）
        """
        if bot_id is None:
            bot_id = next(iter(self.bots.ids.values()), None)
        if not bot_id:
            raise LINEOAError("No bot found")
        now = int(time.time() * 1000)
        send_id = f"{user_id}_{now}_{random.randint(1000000,9999999)}"
        payload = {
            "id": "",
            "type": "textV2",
            "text": context,
            "sendId": send_id
        }
        return self._chat_service.send_message(
            bot_id, user_id, payload, session=self._session, xsrf_token=self._xsrf_token
        )

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
                    raise LINEOAError(f"get Provider Not found: {resp.status_code} {resp.text}")
            except Exception as e:
                self._provider = []
                raise LINEOAError(f"get Provider Error: {e}")
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

class ChatsInfo:
    def __init__(self, chats_list: List[Dict[str, Any]]):
        self._chats = chats_list
        self.group = ChatTypeIds(self._chats, "GROUP")
        self.user = ChatTypeIds(self._chats, "USER")

class ChatTypeIds:
    def __init__(self, chats: List[Dict[str, Any]], chat_type: str):
        self._ids = [c["chatId"] for c in chats if c.get("chatType") == chat_type]
    @property
    def ids(self) -> List[str]:
        return self._ids

