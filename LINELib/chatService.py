import requests
import sseclient
import os
import time
import random
import json
from typing import Optional, Dict, Any, Callable, Generator
from .exceptions import LINEOAError
from .util import merge_dicts
import requests as _requests
from .logger import lineoa_logger

class ChatService:
    def __init__(self, access_token=None):
        self.v1_BASE_URL = "https://chat.line.biz/api/v1"
        self.v2_BASE_URL = "https://chat.line.biz/api/v2"
        self.access_token = access_token
        self.chat_client_version = "20240513144702"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}" if self.access_token else "",
            "Content-Type": "application/json"
        }

    def send_image(self, bot_id, chat_id, image_path, session=None, xsrf_token=None):
        """
        Upload and send an image file to a chat.
        Args:
            bot_id: Bot ID
            chat_id: Chat ID
            image_path: Path to image file
            session: Authenticated requests.Session
            xsrf_token: XSRF token
        Returns:
            dict: API response
        """
        req = session if session else requests
        cookie_dict = {}
        if isinstance(req, _requests.Session):
            for dom in ["chat.line.biz", ".chat.line.biz", "manager.line.biz", ".line.biz"]:
                cookie_dict.update(req.cookies.get_dict(domain=dom))
        if cookie_dict:
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
        else:
            cookie_str = ""
        url_upload = f"https://chat.line.biz/api/v1/bots/{bot_id}/messages/{chat_id}/uploadFile"
        headers_upload = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://chat.line.biz",
            "Referer": f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "x-oa-chat-client-version": self.chat_client_version,
            "Cookie": cookie_str,
            "Content-Type": "application/json",
        }
        if xsrf_token:
            headers_upload["X-XSRF-TOKEN"] = xsrf_token
        with open(image_path, "rb") as f:
            files = {"file": (os.path.basename(image_path), f, "image/png")}
            resp_upload = req.post(url_upload, headers=headers_upload, files=files)
        if not resp_upload.ok:
            raise LINEOAError(f"uploadFile failed: {resp_upload.status_code} {resp_upload.text}")
        token = resp_upload.json().get("contentMessageToken")
        if not token:
            raise LINEOAError("No contentMessageToken returned")
        url_bulk = f"https://chat.line.biz/api/v1/bots/{bot_id}/chats/{chat_id}/messages/bulkSendFiles"
        headers_bulk = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://chat.line.biz",
            "Referer": f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "x-oa-chat-client-version": self.chat_client_version,
            "Cookie": cookie_str,
            "Content-Type": "application/json",
        }
        if xsrf_token:
            headers_bulk["x-xsrf-token"] = xsrf_token
        send_id = f"{chat_id}_{int(time.time()*1000)}_{random.randint(1000000,9999999)}"
        payload = {"items": [{"sendId": send_id, "contentMessageToken": token}]}
        resp_bulk = req.post(url_bulk, headers=headers_bulk, json=payload)
        if not resp_bulk.ok:
            raise LINEOAError(f"bulkSendFiles failed: {resp_bulk.status_code} {resp_bulk.text}")
        return resp_bulk.json()

    def listen_messages(self, bot_id: str, chat_id: str, on_message: Optional[Callable[[Dict[str, Any]], None]] = None, session: Optional[requests.Session] = None) -> None:
        """
        Listen for real-time messages in a chat (SSE).
        Args:
            bot_id: Bot ID
            chat_id: Chat ID
            on_message: Callback for new messages
        """
        url = f"https://chat.line.biz/api/v3/bots/{bot_id}/chats/{chat_id}/events"
        headers = {
            "accept": "text/event-stream",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "ja,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
            "priority": "u=1, i",
            "referer": f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
            "x-oa-chat-client-version": self.chat_client_version
        }
        xsrf_token = None
        req = session if session else requests
        if isinstance(req, _requests.Session):
            for c in req.cookies:
                if c.name == "XSRF-TOKEN" and "chat.line.biz" in c.domain:
                    xsrf_token = c.value
                    break
        if xsrf_token:
            headers["X-XSRF-TOKEN"] = xsrf_token
        resp = req.get(url, headers=headers, stream=True)
        if resp.status_code != 200:
            lineoa_logger.error(f"[listen_messages] HTTP {resp.status_code}: {resp.text}")
            return
        client = sseclient.SSEClient(resp)
        for event in client:
            if event.event == "chat":
                data = json.loads(event.data)
                if on_message:
                    on_message(data)
                else:
                    lineoa_logger.info(f"[SSE chat event] {data}")

    def get_chat_messages(self, bot_id: str, chat_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None, limit: int = 50, before: Optional[str] = None, after: Optional[str] = None) -> Dict[str, Any]:
        """
        Get message list for a chat (matches official web client).
        Args:
            bot_id: Bot ID
            chat_id: Chat ID
            session: Authenticated requests.Session
            xsrf_token: XSRF token
            limit: Number of messages
            before: Message ID before
            after: Message ID after
        Returns:
            dict: List of messages
        """
        url = f"https://chat.line.biz/api/v3/bots/{bot_id}/chats/{chat_id}/messages"
        params = {"limit": int(limit)}
        if before is not None and before.isdigit():
            params["before"] = int(before)
        if after is not None and after.isdigit():
            params["after"] = int(after)
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "ja,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
            "priority": "u=1, i",
            "referer": f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
            "x-oa-chat-client-version": self.chat_client_version,
        }
        req = session if session else requests
        cookie_dict = {}
        xsrf_cookie = None
        if isinstance(req, _requests.Session):
            for dom in ["chat.line.biz", ".chat.line.biz", "manager.line.biz", ".line.biz"]:
                cookie_dict.update(req.cookies.get_dict(domain=dom))
            for c in req.cookies:
                if c.name == "XSRF-TOKEN" and "chat.line.biz" in c.domain:
                    xsrf_cookie = c.value
                    break
        if cookie_dict:
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
            headers["cookie"] = cookie_str
        if xsrf_token:
            headers["X-XSRF-TOKEN"] = xsrf_token
        elif xsrf_cookie:
            headers["X-XSRF-TOKEN"] = xsrf_cookie
        else:
            csrf_resp = requests.get("https://chat.line.biz/api/v1/csrfToken", headers=headers)
            if csrf_resp.ok:
                csrf_json = csrf_resp.json()
                token = csrf_json.get("token")
                if token:
                    headers["X-XSRF-TOKEN"] = token
        resp = req.get(url, headers=headers, params=params)
        if not resp.ok:
            raise LINEOAError(f"get_chat_messages failed: {resp.status_code} {resp.text}")
        return resp.json()

    def get_chats(self, bot_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Get chat list for a bot (matches browser).
        Args:
            bot_id: Bot ID
            session: Authenticated requests.Session
            xsrf_token: XSRF token
        Returns:
            dict: List of chats
        """
        url = f"https://manager.line.biz/api/bots/{bot_id}/recentChats"
        browser_headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": f"https://manager.line.biz/account/{bot_id}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "X-BotCms-ScriptRevision": "74.0.0",
            "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "x-oa-chat-client-version": self.chat_client_version,
        }
        req = session if session else requests
        cookie_header = {}
        xsrf_cookie = None
        if isinstance(req, _requests.Session):
            cookies_manager = req.cookies.get_dict(domain="manager.line.biz")
            cookies_chat = req.cookies.get_dict(domain="chat.line.biz")
            cookie_header = {**cookies_chat, **cookies_manager}
            for c in req.cookies:
                if c.name == "XSRF-TOKEN" and "chat.line.biz" in c.domain:
                    xsrf_cookie = c.value
                    break
            if cookie_header:
                cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_header.items())
                browser_headers["Cookie"] = cookie_str
            print("[DEBUG] get_chats cookies (merged):", cookie_header)
        if xsrf_token:
            browser_headers["X-XSRF-TOKEN"] = xsrf_token
        elif xsrf_cookie:
            browser_headers["X-XSRF-TOKEN"] = xsrf_cookie
        else:
            csrf_resp = requests.get("https://chat.line.biz/api/v1/csrfToken", headers=browser_headers)
            if csrf_resp.ok:
                csrf_json = csrf_resp.json()
                token = csrf_json.get("token")
                if token:
                    browser_headers["X-XSRF-TOKEN"] = token
        resp = req.get(url, headers=browser_headers)
        if not resp.ok:
            raise LINEOAError(f"get_chats failed: {resp.status_code} {resp.text}")
        return resp.json()

    def get_me(self) -> Dict[str, Any]:
        """
        Get own account info.
        Returns:
            dict: Account info
        """
        url = "https://chat.line.biz/api/v1/me"
        try:
            response = requests.get(url, headers=self.headers)
            self._handle_response(response)
            return response.json()
        except Exception as e:
            print(f"get_me: {e}")
            raise LINEOAError(f"get_me: {e}")

    def get_bot_account(self, bot_id: str, no_filter: bool = True) -> Dict[str, Any]:
        """
        Get account info for a bot.
        Args:
            bot_id: Bot ID
            no_filter: Disable filter
        Returns:
            dict: Bot info
        """
        url = f"https://chat.line.biz/api/v1/bots/{bot_id}"
        params = {"noFilter": str(no_filter).lower()}
        try:
            response = requests.get(url, headers=self.headers, params=params)
            self._handle_response(response)
            return response.json()
        except Exception as e:
            print(f"get_bot_account: {e}")
            raise LINEOAError(f"get_bot_account: {e}")

    def get_csrf_token(self) -> Dict[str, Any]:
        """
        Get CSRF token.
        Returns:
            dict: CSRF token info
        """
        url = "https://chat.line.biz/api/v1/csrfToken"
        try:
            response = requests.get(url, headers=self.headers)
            self._handle_response(response)
            return response.json()
        except Exception as e:
            print(f"get_csrf_token: {e}")
            raise LINEOAError(f"get_csrf_token: {e}")

    def get_bot_accounts(self, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None, limit: int = 1000, no_filter: bool = True) -> Dict[str, Any]:
        """
        Get bot account list.
        Args:
            session: Authenticated requests.Session
            xsrf_token: XSRF token
            limit: Max number of accounts
            no_filter: Disable filter
        Returns:
            dict: List of bot accounts
        """
        url = f"https://chat.line.biz/api/v1/bots"
        params = {"limit": limit, "noFilter": str(no_filter).lower()}
        browser_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "x-oa-chat-client-version": self.chat_client_version,
        }
        if xsrf_token:
            browser_headers["x-xsrf-token"] = xsrf_token
        req = session if session else requests
        resp = req.get(url, headers=browser_headers, params=params)
        if not resp.ok:
            raise LINEOAError(f"get_bot_accounts failed: {resp.status_code} {resp.text}")
        return resp.json()

    def get_pinned_messages(self, bot_id: str, chat_id: str) -> Dict[str, Any]:
        """
        Get pinned messages in a chat.
        Args:
            bot_id: Bot ID
            chat_id: Chat ID
        Returns:
            dict: Pinned messages
        """
        url = f"{self.v2_BASE_URL}/bots/{bot_id}/chats/{chat_id}/messages/pin"
        try:
            response = requests.get(url, headers=self.headers)
            self._handle_response(response)
            return response.json()
        except Exception as e:
            raise LINEOAError(f"get_pinned_messages: {e}")

    def set_typing(self, bot_id: str, chat_id: str) -> Dict[str, Any]:
        """
        Send typing indicator to chat.
        Args:
            bot_id: Bot ID
            chat_id: Chat ID
        Returns:
            dict: Always empty
        """
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/chats/{chat_id}/typing"
        try:
            response = requests.put(url, headers=self.headers)
            self._handle_response(response)
            return {}
        except Exception as e:
            raise LINEOAError(f"set_typing: {e}")

    def streaming_state(self, bot_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Set streaming state for bot.
        Args:
            bot_id: Bot ID
            state: Streaming state dict
        Returns:
            dict: Always empty
        """
        if not state or "connectionId" not in state or "idle" not in state:
            raise LINEOAError("require state 'connectionId' and 'idle' fields")
        payload = merge_dicts({}, state)
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/streaming/state"
        try:
            response = requests.put(url, headers=self.headers, json=payload)
            self._handle_response(response)
            return {}
        except Exception as e:
            raise LINEOAError(f"streaming_state: {e}")

    def get_streaming_api_token(self, bot_id: str) -> Dict[str, Any]:
        """
        Get streaming API token for bot.
        Args:
            bot_id: Bot ID
        Returns:
            dict: API response
        """
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/streamingApiToken"
        try:
            response = requests.post(url, headers=self.headers)
            self._handle_response(response)
            return response.json()
        except Exception as e:
            raise LINEOAError(f"get_streaming_api_token: {e}")

    def stream_events(self, streaming_api_token: str, device_type: str = "", client_type: str = "PC", ping_secs: int = 60, last_event_id: Optional[str] = None, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Stream events from SSE endpoint.
        Args:
            streaming_api_token: SSE token
            device_type: Device type
            client_type: Client type
            ping_secs: Ping interval
            last_event_id: Previous event ID
            session: Authenticated requests.Session
            xsrf_token: XSRF token
        Yields:
            dict: Event data
        """
        base_url = "https://chat-streaming-api.line.biz/api/v2/sse"
        params = {
            "token": streaming_api_token,
            "deviceType": device_type,
            "clientType": client_type,
            "pingSecs": ping_secs
        }
        if last_event_id:
            params["lastEventId"] = last_event_id
        headers = {
            "accept": "text/event-stream",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "ja,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
            "cache-control": "no-cache",
            "origin": "https://chat.line.biz",
            "referer": "https://chat.line.biz/",
            "priority": "u=1, i",
            "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
        }
        if xsrf_token:
            headers["X-XSRF-TOKEN"] = xsrf_token
        if session:
            cookie_dict = {}
            for c in session.cookies:
                if "chat.line.biz" in c.domain:
                    cookie_dict[c.name] = c.value
            for c in session.cookies:
                if c.name in ["__Host-chat-ses", "chat-device-group", "XSRF-TOKEN"]:
                    cookie_dict[c.name] = str(c.value)
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
            headers["cookie"] = cookie_str
            req = session
        else:
            req = requests
        with req.get(base_url, headers=headers, params=params, stream=True, timeout=90) as resp:
            if not resp.ok:
                raise LINEOAError(f"HTTP {resp.status_code}: {resp.text}")
            client = sseclient.SSEClient(resp)
            for event in client:
                if event.data is not None:
                    try:
                        yield {
                            "id": getattr(event, "id", None),
                            "type": getattr(event, "event", None),
                            "data": event.data,
                            "time": time.strftime("%H:%M:%S.%f", time.localtime())[:-3]
                        }
                    except Exception:
                        pass

    def send_message(self, bot_id: str, chat_id: str, message: Dict[str, Any], session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a message to a chat.
        Args:
            bot_id: Bot ID
            chat_id: Chat ID
            message: Message dict
            session: Authenticated requests.Session
            xsrf_token: XSRF token
        Returns:
            dict: Always empty
        """
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/chats/{chat_id}/messages/send"
        browser_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Referer": f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            "Origin": "https://chat.line.biz",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "x-oa-chat-client-version": self.chat_client_version,
            "Content-Type": "application/json",
        }
        if xsrf_token:
            browser_headers["x-xsrf-token"] = xsrf_token
        req = session if session else requests
        cookie_dict = {}
        if isinstance(req, _requests.Session):
            for dom in ["chat.line.biz", ".chat.line.biz", "manager.line.biz", ".line.biz"]:
                cookie_dict.update(req.cookies.get_dict(domain=dom))
        if cookie_dict:
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
            browser_headers["Cookie"] = cookie_str
        browser_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36"
        browser_headers["sec-ch-ua"] = '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"'
        browser_headers["sec-ch-ua-mobile"] = "?0"
        browser_headers["sec-ch-ua-platform"] = '"Windows"'
        browser_headers["Accept-Language"] = "ja,en-US;q=0.9,en;q=0.8"
        browser_headers["Sec-Fetch-Site"] = "same-origin"
        browser_headers["Sec-Fetch-Mode"] = "cors"
        browser_headers["Sec-Fetch-Dest"] = "empty"
        browser_headers["x-oa-chat-client-version"] = "20240513144702"
        browser_headers["Content-Type"] = "application/json"
        browser_headers["Referer"] = f"https://chat.line.biz/{bot_id}/chat/{chat_id}"
        browser_headers["Origin"] = "https://chat.line.biz"
        response = req.post(url, headers=browser_headers, json=message)
        if not response.ok:
            raise LINEOAError(f"HTTP {response.status_code}: {response.text}")
        return {}

    def _handle_response(self, response: requests.Response) -> None:
        if not response.ok:
            raise LINEOAError(f"HTTP {response.status_code}: {response.text}")
