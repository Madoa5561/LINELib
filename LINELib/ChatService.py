import requests
import aiohttp
import os
import time
from datetime import datetime
import random
import json
from typing import Optional, Dict, Any, Callable, Generator
from .exceptions import LINEOAError
from .sse import SSEParser
from .util import merge_dicts
import requests as _requests
from .logger import lineoa_logger

class ChatService:
    def __init__(self):
        self.v1_BASE_URL = "https://chat.line.biz/api/v1"
        self.v2_BASE_URL = "https://chat.line.biz/api/v2"
        self.v3_BASE_URL = "https://chat.line.biz/api/v3"
        self.v4_BASE_URL = "https://chat.line.biz/api/v4"
        self.manager_BASE_URL = "https://manager.line.biz/api"
        self.chat_client_version = "20240513144702"
        self.headers = {
            "Content-Type": "application/json"
        }

    def _base_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
            "Accept": "application/json, text/plain, */*",
            "x-oa-chat-client-version": self.chat_client_version,
        }

    def _session_headers(self, session: Optional[requests.Session], xsrf_token: Optional[str] = None, origin: Optional[str] = None, referer: Optional[str] = None) -> Dict[str, str]:
        headers = self._base_headers()
        if origin:
            headers["Origin"] = origin
        if referer:
            headers["Referer"] = referer
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        if isinstance(session, _requests.Session):
            cookie_dict = {}
            for dom in ["chat.line.biz", ".chat.line.biz", "manager.line.biz", ".line.biz"]:
                try:
                    cookie_dict.update(session.cookies.get_dict(domain=dom))
                except Exception:
                    pass
            if cookie_dict:
                headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
        return headers

    def _get_json(self, url: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None, params: Optional[Dict[str, Any]] = None, origin: Optional[str] = None, referer: Optional[str] = None) -> Dict[str, Any]:
        req = session if session else requests
        resp = req.get(url, headers=self._session_headers(session, xsrf_token=xsrf_token, origin=origin, referer=referer), params=params)
        if not resp.ok:
            raise LINEOAError(f"GET {url} failed: {resp.status_code} {resp.text}")
        return resp.json()

    def _put_json(self, url: str, payload: Optional[Dict[str, Any]] = None, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None, origin: Optional[str] = None, referer: Optional[str] = None) -> Dict[str, Any]:
        req = session if session else requests
        resp = req.put(url, headers=self._session_headers(session, xsrf_token=xsrf_token, origin=origin, referer=referer), json=payload)
        if not resp.ok:
            raise LINEOAError(f"PUT {url} failed: {resp.status_code} {resp.text}")
        return resp.json() if resp.text else {}

    def _post_json(self, url: str, payload: Optional[Dict[str, Any]] = None, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None, origin: Optional[str] = None, referer: Optional[str] = None) -> Dict[str, Any]:
        req = session if session else requests
        resp = req.post(url, headers=self._session_headers(session, xsrf_token=xsrf_token, origin=origin, referer=referer), json=payload)
        if not resp.ok:
            raise LINEOAError(f"POST {url} failed: {resp.status_code} {resp.text}")
        return resp.json() if resp.text else {}

    def send_mention(self, bot_id: str, chat_id: str, mentionee_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        """
            Send a mention message to a chat.
            Args:
                bot_id: Bot ID
                chat_id: Chat ID
                mentionee_id: User ID to mention
                session: Authenticated requests.Session
                xsrf_token: XSRF token
            Returns:
                dict: Always empty
        """
        mention_text = f"@{mentionee_id} "
        payload = {
            "type": "text",
            "text": mention_text,
            "mentions": [
                {
                    "userId": mentionee_id,
                    "offset": 0,
                    "length": len(mention_text)
                }
            ]
        }
        return self.send_message(bot_id, chat_id, payload, session=session, xsrf_token=xsrf_token)

    def send_file(self, bot_id, chat_id, file_path, session=None, xsrf_token=None):
        """
        Upload and send a file (image, etc.) to a chat.
        Args:
            bot_id: Bot ID
            chat_id: Chat ID
            file_path: Path to file (image, etc.)
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
        }
        if xsrf_token:
            headers_upload["X-XSRF-TOKEN"] = xsrf_token
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "application/octet-stream")}
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

    async def async_send_file(self, bot_id: str, chat_id: str, file_path: str, cookies: Optional[Dict[str,str]] = None, xsrf_token: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        """
        Async version of send_file using aiohttp.
        """
        url_upload = f"https://chat.line.biz/api/v1/bots/{bot_id}/messages/{chat_id}/uploadFile"
        headers_upload = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://chat.line.biz",
            "Referer": f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            "x-oa-chat-client-version": self.chat_client_version,
        }
        if xsrf_token:
            headers_upload["X-XSRF-TOKEN"] = xsrf_token
        if cookies:
            headers_upload["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())

        own_session = False
        if session is None:
            session = aiohttp.ClientSession()
            own_session = True
        try:
            data = aiohttp.FormData()
            data.add_field('file', open(file_path, 'rb'), filename=os.path.basename(file_path), content_type='application/octet-stream')
            async with session.post(url_upload, headers=headers_upload, data=data) as resp_upload:
                text = await resp_upload.text()
                if resp_upload.status >= 400:
                    raise LINEOAError(f"uploadFile failed: {resp_upload.status} {text}")
                j = await resp_upload.json()
            token = j.get('contentMessageToken')
            if not token:
                raise LINEOAError('No contentMessageToken returned')

            url_bulk = f"https://chat.line.biz/api/v1/bots/{bot_id}/chats/{chat_id}/messages/bulkSendFiles"
            headers_bulk = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://chat.line.biz",
                "Referer": f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
                "x-oa-chat-client-version": self.chat_client_version,
                "Content-Type": "application/json",
            }
            if xsrf_token:
                headers_bulk["x-xsrf-token"] = xsrf_token
            if cookies:
                headers_bulk["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())

            send_id = f"{chat_id}_{int(time.time()*1000)}_{random.randint(1000000,9999999)}"
            payload = {"items": [{"sendId": send_id, "contentMessageToken": token}]}
            async with session.post(url_bulk, headers=headers_bulk, json=payload) as resp_bulk:
                text = await resp_bulk.text()
                if resp_bulk.status >= 400:
                    raise LINEOAError(f"bulkSendFiles failed: {resp_bulk.status} {text}")
                return await resp_bulk.json()
        finally:
            if own_session:
                await session.close()

    def get_chat_members(self, bot_id: str, chat_id: str, limit: int = 100, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Get chat members for a chat.
        Args:
            bot_id: Bot ID
            chat_id: Chat ID
            limit: Number of members to retrieve
            session: Authenticated requests.Session
            xsrf_token: XSRF token
        Returns:
            dict: List of chat members
        """
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/chats/{chat_id}/members?limit={limit}"
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
            "x-oa-chat-client-version": self.chat_client_version
        }
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        req = session if session else requests
        try:
            has_cookie = 'cookie' in headers and bool(headers.get('cookie'))
            has_xsrf = 'x-xsrf-token' in headers and bool(headers.get('x-xsrf-token'))
            lineoa_logger.info(f"get_chats: url={url} has_cookie={has_cookie} has_xsrf={has_xsrf}")
        except Exception:
            pass
        resp = req.get(url, headers=headers)
        if not resp.ok:
            raise LINEOAError(f"get_chat_members failed: {resp.status_code} {resp.text}")
        return resp.json()

    async def async_get_chat_members(self, bot_id: str, chat_id: str, limit: int = 100, cookies: Optional[Dict[str,str]] = None, xsrf_token: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/chats/{chat_id}/members?limit={limit}"
        headers = {
            "accept": "application/json, text/plain, */*",
            "x-oa-chat-client-version": self.chat_client_version,
        }
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        if cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
        own_session = False
        if session is None:
            session = aiohttp.ClientSession()
            own_session = True
        try:
            async with session.get(url, headers=headers) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise LINEOAError(f"get_chat_members failed: {resp.status} {text}")
                return await resp.json()
        finally:
            if own_session:
                await session.close()

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
        for event in SSEParser.iter_events(resp.iter_lines(decode_unicode=True)):
            if event.event not in (None, "chat"):
                continue
            data = event.payload
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
            csrf_resp = req.get("https://chat.line.biz/api/v1/csrfToken", headers=headers)
            if csrf_resp.ok:
                csrf_json = csrf_resp.json()
                token = csrf_json.get("token")
                if token:
                    headers["X-XSRF-TOKEN"] = token
        resp = req.get(url, headers=headers, params=params)
        if not resp.ok:
            raise LINEOAError(f"get_chat_messages failed: {resp.status_code} {resp.text}")
        return resp.json()

    async def async_get_chat_messages(self, bot_id: str, chat_id: str, cookies: Optional[Dict[str,str]] = None, xsrf_token: Optional[str] = None, limit: int = 50, before: Optional[str] = None, after: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        url = f"{self.v2_BASE_URL}/bots/{bot_id}/chats/{chat_id}/messages"
        params = {"limit": int(limit)}
        if before is not None and before.isdigit():
            params["before"] = int(before)
        if after is not None and after.isdigit():
            params["after"] = int(after)
        headers = {
            "accept": "application/json, text/plain, */*",
            "x-oa-chat-client-version": self.chat_client_version,
        }
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        if cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
        own_session = False
        if session is None:
            session = aiohttp.ClientSession()
            own_session = True
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise LINEOAError(f"get_chat_messages failed: {resp.status} {text}")
                return await resp.json()
        finally:
            if own_session:
                await session.close()

    def get_chats(
        self,
        bot_id: str,
        session: Optional[requests.Session] = None,
        xsrf_token: Optional[str] = None,
        folder_type: str = "ALL",
        tag_ids: str = "",
        auto_tag_ids: str = "",
        limit: int = 25,
        prioritize_pinned_chat: bool = True,
    ) -> Dict[str, Any]:
        """
        Get chat list for a bot (matches browser /api/v2).
        Args:
            bot_id: Bot ID
            session: Authenticated requests.Session
            xsrf_token: XSRF token
            folder_type: Chat folder type (default "ALL")
            tag_ids: Tag IDs (comma-separated)
            auto_tag_ids: Auto tag IDs (comma-separated)
            limit: Number of chats to retrieve
            prioritize_pinned_chat: Prioritize pinned chats
        Returns:
            dict: List of chats
        """
        url = (
            f"https://chat.line.biz/api/v2/bots/{bot_id}/chats"
            f"?folderType={folder_type}"
            f"&tagIds={tag_ids}"
            f"&autoTagIds={auto_tag_ids}"
            f"&limit={limit}"
            f"&prioritizePinnedChat={'true' if prioritize_pinned_chat else 'false'}"
        )
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "ja,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
            "priority": "u=1, i",
            "referer": f"https://chat.line.biz/{bot_id}",
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
                try:
                    cookie_dict.update(req.cookies.get_dict(domain=dom))
                except Exception:
                    pass
            for c in req.cookies:
                domain = getattr(c, 'domain', '')
                name = getattr(c, 'name', None)
                if name == "XSRF-TOKEN" and "chat.line.biz" in domain:
                    xsrf_cookie = c.value
                    break
        if cookie_dict:
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
            headers["cookie"] = cookie_str
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        elif xsrf_cookie:
            headers["x-xsrf-token"] = xsrf_cookie
        else:
            try:
                csrf_resp = requests.get("https://chat.line.biz/api/v1/csrfToken", headers=headers)
                if csrf_resp.ok:
                    csrf_json = csrf_resp.json()
                    token = csrf_json.get("token")
                    if token:
                        headers["x-xsrf-token"] = token
            except Exception:
                pass
        resp = req.get(url, headers=headers)
        if not resp.ok:
            raise LINEOAError(f"get_chats failed: {resp.status_code} {resp.text}")
        return resp.json()

    def get_me(self) -> Dict[str, Any]:
        """
        Get own account info.
        Returns:
            dict: Account info
        """
        return self._get_json("https://chat.line.biz/api/v1/me")

    def get_bot_account(self, bot_id: str, no_filter: bool = True) -> Dict[str, Any]:
        """
        Get account info for a bot.
        Args:
            bot_id: Bot ID
            no_filter: Disable filter
        Returns:
            dict: Bot info
        """
        url = f"{self.v1_BASE_URL}/bots/{bot_id}"
        params = {"noFilter": str(no_filter).lower()}
        return self._get_json(url, params=params)

    def get_csrf_token(self) -> Dict[str, Any]:
        """
        Get CSRF token.
        Returns:
            dict: CSRF token info
        """
        return self._get_json("https://chat.line.biz/api/v1/csrfToken")

    def get_whitelist_domains(self) -> Dict[str, Any]:
        return self._get_json("https://chat.line.biz/api/v1/whitelistDomains")

    def get_me_settings_pc(self) -> Dict[str, Any]:
        return self._get_json("https://chat.line.biz/api/v1/me/settings/pc")

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
        return self._get_json(url)

    def get_chat(self, bot_id: str, chat_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v1_BASE_URL}/bots/{bot_id}/chats/{chat_id}", session=session, xsrf_token=xsrf_token, referer=f"https://chat.line.biz/{bot_id}/chat/{chat_id}", origin="https://chat.line.biz")

    def get_chat_mode(self, bot_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v4_BASE_URL}/bots/{bot_id}/settings/chatMode", session=session, xsrf_token=xsrf_token)

    def get_chat_mode_schedules(self, bot_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v1_BASE_URL}/bots/{bot_id}/settings/chatModeSchedules", session=session, xsrf_token=xsrf_token)

    def get_available_features(self, bot_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v2_BASE_URL}/bots/{bot_id}/availableFeatures", session=session, xsrf_token=xsrf_token)

    def get_banner_web(self, bot_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v2_BASE_URL}/bots/{bot_id}/banner/web", session=session, xsrf_token=xsrf_token)

    def get_call_session(self, bot_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v1_BASE_URL}/bots/{bot_id}/callSession", session=session, xsrf_token=xsrf_token)

    def get_activities(self, bot_id: str, chat_id: str, limit: int = 1, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v1_BASE_URL}/bots/{bot_id}/chats/{chat_id}/activities", session=session, xsrf_token=xsrf_token, params={"limit": limit})

    def get_notes(self, bot_id: str, chat_id: str, limit: int = 20, with_total: bool = True, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v1_BASE_URL}/bots/{bot_id}/chats/{chat_id}/notes", session=session, xsrf_token=xsrf_token, params={"limit": limit, "withTotal": str(with_total).lower()})

    def get_authorized_users(self, bot_id: str, biz_ids: str = "__AUTO_RESPONSE", session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v1_BASE_URL}/bots/{bot_id}/authorizedUsers", session=session, xsrf_token=xsrf_token, params={"bizIds": biz_ids})

    def get_use_manual_chat(self, bot_id: str, chat_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v2_BASE_URL}/bots/{bot_id}/chats/{chat_id}/useManualChat", session=session, xsrf_token=xsrf_token)

    def get_recent_stickers(self, bot_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v1_BASE_URL}/bots/{bot_id}/stickers/recently", session=session, xsrf_token=xsrf_token)

    def get_recent_emojis(self, bot_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v1_BASE_URL}/bots/{bot_id}/emojis/recently", session=session, xsrf_token=xsrf_token)

    def get_saved_replies(self, bot_id: str, query: str = "", exclude_username_placeholder: bool = False, sort_key: str = "CREATED_AT", page_size: int = 25, page: int = 1, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v2_BASE_URL}/bots/{bot_id}/savedReplies", session=session, xsrf_token=xsrf_token, params={"query": query, "excludeUsernamePlaceholder": str(exclude_username_placeholder).lower(), "sortKey": sort_key, "pageSize": page_size, "page": page})

    def get_clock_now(self, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v1_BASE_URL}/clock/now", session=session, xsrf_token=xsrf_token)

    def get_holiday(self, country: str = "JP", session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v1_BASE_URL}/holiday/{country}", session=session, xsrf_token=xsrf_token)

    def get_plugins(self, bot_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json(f"{self.v1_BASE_URL}/bots/{bot_id}/plugins", session=session, xsrf_token=xsrf_token)

    def get_content_preview(self, bot_id: str, content_hash: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> bytes:
        url = f"https://chat-content.line.biz/bot/{bot_id}/{content_hash}/preview"
        req = session if session else requests
        resp = req.get(
            url,
            headers={
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                "User-Agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36",
            },
        )
        if not resp.ok:
            raise LINEOAError(f"get_content_preview failed: {resp.status_code} {resp.text}")
        return resp.content

    def get_sticker_image(self, sticker_id: str, session: Optional[requests.Session] = None) -> bytes:
        url = f"https://stickershop.line-scdn.net/stickershop/v1/sticker/{sticker_id}/android/sticker.png"
        req = session if session else requests
        resp = req.get(
            url,
            headers={
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                "User-Agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36",
            },
        )
        if not resp.ok:
            raise LINEOAError(f"get_sticker_image failed: {resp.status_code} {resp.text}")
        return resp.content

    def save_sticker_image(self, sticker_id: str, file_path: str, session: Optional[requests.Session] = None) -> str:
        data = self.get_sticker_image(sticker_id=sticker_id, session=session)
        with open(file_path, "wb") as f:
            f.write(data)
        return file_path

    def save_content_preview(self, bot_id: str, content_hash: str, file_path: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> str:
        data = self.get_content_preview(bot_id=bot_id, content_hash=content_hash, session=session, xsrf_token=xsrf_token)
        with open(file_path, "wb") as f:
            f.write(data)
        return file_path

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

    def get_streaming_api_token(self, bot_id: str, session: Optional[object] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Get streaming API token for bot.
        Args:
            bot_id: Bot ID
        Returns:
            dict: API response
        """
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/streamingApiToken"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://chat.line.biz",
            "Referer": f"https://chat.line.biz/{bot_id}/chat/",
            "x-oa-chat-client-version": self.chat_client_version,
        }
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        req = session if session else requests
        try:
            response = req.post(url, headers=headers, data="")
            self._handle_response(response)
            payload = response.json()
            if "streamingApiBaseUrl" not in payload:
                payload["streamingApiBaseUrl"] = "https://chat-streaming-api.line.biz"
            if "streamingApiVersion" not in payload:
                payload["streamingApiVersion"] = "v2"
            return payload
        except Exception as e:
            raise LINEOAError(f"get_streaming_api_token: {e}")

    def stream_events(self, streaming_api_token: str, device_type: str = "", client_type: str = "PC", ping_secs: int = 60, last_event_id: Optional[str] = None, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None, max_stream_seconds: float = 82800, base_url: str = "https://chat-streaming-api.line.biz", version: str = "v2") -> Generator[Dict[str, Any], None, None]:
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
        base_url = f"{base_url}/api/{version}/sse"
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
        started_at = time.monotonic()
        with req.get(base_url, headers=headers, params=params, stream=True, timeout=90) as resp:
            if not resp.ok:
                raise LINEOAError(f"HTTP {resp.status_code}: {resp.text}")
            event_id = None
            event_type = None
            data_lines = []
            for line in resp.iter_lines(decode_unicode=True):
                if time.monotonic() - started_at >= max_stream_seconds:
                    break
                if line is None:
                    continue
                line = line.strip()
                if line.startswith(":") or not line:
                    if data_lines:
                        data = "\n".join(data_lines)
                        try:
                            payload = json.loads(data)
                        except Exception:
                            payload = data
                        result = {
                            "id": event_id,
                            "type": event_type,
                            "payload": payload,
                            "time": datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        }
                        yield result
                        data_lines = []
                        event_id = None
                        event_type = None
                    continue
                if line.startswith("id:"):
                    event_id = line[3:].strip()
                elif line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].strip())
                else:
                    continue

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

    async def async_send_message(self, bot_id: str, chat_id: str, message: Dict[str, Any], cookies: Optional[Dict[str, str]] = None, xsrf_token: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        """
        Async version of send_message using aiohttp.
        cookies: dict of cookie name->value to send in Cookie header.
        """
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/chats/{chat_id}/messages/send"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            "Origin": "https://chat.line.biz",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "x-oa-chat-client-version": self.chat_client_version,
            "Content-Type": "application/json",
        }
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        if cookies:
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
            headers["Cookie"] = cookie_str

        own_session = False
        if session is None:
            session = aiohttp.ClientSession()
            own_session = True
        try:
            async with session.post(url, headers=headers, json=message) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise LINEOAError(f"HTTP {resp.status}: {text}")
        finally:
            if own_session:
                await session.close()
        return {}

    def send_flex_message(
        self,
        bot_id: str,
        chat_id: str,
        card_type_message_id: int,
        session: Optional[requests.Session] = None,
        xsrf_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a Flex (cardType) message to a chat.
        Args:
            bot_id: Bot ID
            chat_id: Chat ID
            card_type_message_id: Flex message template ID (cardTypeMessageId)
            session: Authenticated requests.Session
            xsrf_token: XSRF token
        Returns:
            dict: Always empty on success
        """
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/chats/{chat_id}/messages/send"
        send_id = f"{chat_id}_{int(time.time() * 1000)}_{random.randint(1000000, 9999999)}"
        payload = {
            "id": "",
            "type": "cardType",
            "cardTypeMessageId": card_type_message_id,
            "sendId": send_id,
        }
        browser_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36",
            "sec-ch-ua": '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://chat.line.biz",
            "Referer": f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "x-oa-chat-client-version": self.chat_client_version,
        }
        if xsrf_token:
            browser_headers["x-xsrf-token"] = xsrf_token
        req = session if session else requests
        cookie_dict = {}
        if isinstance(req, _requests.Session):
            for dom in ["chat.line.biz", ".chat.line.biz", "manager.line.biz", ".line.biz"]:
                cookie_dict.update(req.cookies.get_dict(domain=dom))
        if cookie_dict:
            browser_headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
        response = req.post(url, headers=browser_headers, json=payload)
        if not response.ok:
            raise LINEOAError(f"send_flex_message failed: HTTP {response.status_code}: {response.text}")
        return {}

    def get_flex_json(
        self,
        bot_id: str,
        chat_id: str,
        message_id: str,
        timestamp: Optional[int] = None,
        session: Optional[requests.Session] = None,
        xsrf_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve the Flex JSON of a sent cardType message.
        Args:
            bot_id: Bot ID
            chat_id: Chat ID
            message_id: Message ID returned after sending
            timestamp: Message timestamp in milliseconds (defaults to now)
            session: Authenticated requests.Session
            xsrf_token: XSRF token
        Returns:
            dict: Flex JSON payload
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/chats/{chat_id}/messages/flexJson"
        params = {"timestamp": timestamp, "messageId": message_id}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://chat.line.biz",
            "Referer": f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            "x-oa-chat-client-version": self.chat_client_version,
        }
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        req = session if session else requests
        cookie_dict = {}
        if isinstance(req, _requests.Session):
            for dom in ["chat.line.biz", ".chat.line.biz", "manager.line.biz", ".line.biz"]:
                cookie_dict.update(req.cookies.get_dict(domain=dom))
        if cookie_dict:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
        response = req.get(url, headers=headers, params=params)
        if not response.ok:
            raise LINEOAError(f"get_flex_json failed: HTTP {response.status_code}: {response.text}")
        return response.json()

    def mark_as_read(
        self,
        bot_id: str,
        chat_id: str,
        message_id: str,
        timestamp: Optional[int] = None,
        session: Optional[requests.Session] = None,
        xsrf_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Mark a chat as read up to the specified message.
        Args:
            bot_id: Bot ID
            chat_id: Chat ID
            message_id: ID of the last message to mark as read
            timestamp: Timestamp of the message in milliseconds (defaults to now)
            session: Authenticated requests.Session
            xsrf_token: XSRF token
        Returns:
            dict: Always empty on success
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)
        url = f"{self.v2_BASE_URL}/bots/{bot_id}/chats/{chat_id}/markAsRead"
        payload = {
            "lastMessage": {
                "messageId": message_id,
                "timestamp": timestamp,
            }
        }
        browser_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36",
            "sec-ch-ua": '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://chat.line.biz",
            "Referer": f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "x-oa-chat-client-version": self.chat_client_version,
        }
        if xsrf_token:
            browser_headers["x-xsrf-token"] = xsrf_token
        req = session if session else requests
        cookie_dict = {}
        if isinstance(req, _requests.Session):
            for dom in ["chat.line.biz", ".chat.line.biz", "manager.line.biz", ".line.biz"]:
                cookie_dict.update(req.cookies.get_dict(domain=dom))
        if cookie_dict:
            browser_headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
        response = req.put(url, headers=browser_headers, json=payload)
        if not response.ok:
            raise LINEOAError(f"mark_as_read failed: HTTP {response.status_code}: {response.text}")
        return {}


    def _manager_headers(self, session, at_id: str, xsrf_token=None) -> dict:
        """manager.line.biz 用ヘッダー生成"""
        import requests as _req
        cookie_dict = {}
        if isinstance(session, _req.Session):
            for dom in ["manager.line.biz", ".line.biz", ".manager.line.biz", "chat.line.biz", ".chat.line.biz"]:
                cookie_dict.update(session.cookies.get_dict(domain=dom))
        h = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://manager.line.biz",
            "Referer": f"https://manager.line.biz/",
            "Cookie": "; ".join(f"{k}={v}" for k, v in cookie_dict.items()),
        }
        if xsrf_token:
            h["x-xsrf-token"] = xsrf_token
        return h

    def create_card_type_message(
        self,
        at_id: str,
        title: str,
        image_url: str,
        tag_name: str = "",
        tag_color: str = "info",
        description: str = "",
        action_label: str = "",
        action_text: str = "",
        session=None,
        xsrf_token: str = None,
    ) -> int:
        """
        manager.line.biz 経由でカードメッセージを動的作成し、IDを返す。
        Args:
            at_id       : Bot の @ID（例: "@318ogzps" または "318ogzps"）
            title       : カードタイトル（OA Manager上の管理名 & 表示タイトル）
            image_url   : ヒーロー画像URL
            tag_name    : タグテキスト（空文字で非表示）
            tag_color   : タグ色 ("info" / "success" / "warning" / "danger" など)
            description : 説明文（空文字で非表示）
            action_label: ボタンラベル
            action_text : ボタン押下時に送信されるテキスト
            session     : requests.Session
            xsrf_token  : XSRF トークン
        Returns:
            int: 作成されたカードの cardTypeMessageId
        """
        at_id = at_id.lstrip("@")
        url = f"https://manager.line.biz/api/bots/@{at_id}/cardTypeMessages"
        payload = {
            "title": title,
            "type": "Product",
            "actions": [],
            "origin": {
                "title": title,
                "type": "Product",
                "messages": [
                    {
                        "title": title,
                        "icon": {
                            "enable": bool(tag_name),
                            "name": tag_name,
                            "color": tag_color,
                            "widthMeasurement": 25.7587890625,
                        },
                        "image": {
                            "isNoImage": not bool(image_url),
                            "maxFile": 1,
                            "list": [{"src": image_url}] if image_url else [],
                        },
                        "description": {
                            "enable": bool(description),
                            "value": description,
                        },
                        "price": {"enable": False, "value": "", "unit": ""},
                        "links": [
                            {
                                "enable": bool(action_label),
                                "title": action_label,
                                "type": "Text",
                                "shopCard": "",
                                "message": action_text,
                            },
                            {"enable": False, "title": "", "type": "Choice", "url": ""},
                        ],
                    }
                ],
                "viewmore": {
                    "enable": False,
                    "type": "ADDITIONAL_SIMPLE",
                    "images": [{"src": ""}],
                    "link": {"enable": True, "title": "", "type": "Choice", "url": ""},
                },
            },
        }
        req = session if session else requests
        headers = self._manager_headers(session, at_id, xsrf_token)
        response = req.post(url, headers=headers, json=payload)
        if not response.ok:
            raise LINEOAError(f"create_card_type_message failed: HTTP {response.status_code}: {response.text}")
        card_id = response.json().get("id")
        if not card_id:
            raise LINEOAError(f"create_card_type_message: no id in response: {response.text}")
        return int(card_id)

    def delete_card_type_message(
        self,
        at_id: str,
        card_id: int,
        session=None,
        xsrf_token: str = None,
    ) -> None:
        """
        作成したカードメッセージを削除する。
        Args:
            at_id   : Bot の @ID
            card_id : create_card_type_message で取得した ID
        """
        at_id = at_id.lstrip("@")
        url = f"https://manager.line.biz/api/bots/@{at_id}/cardTypeMessages/{card_id}"
        req = session if session else requests
        headers = self._manager_headers(session, at_id, xsrf_token)
        response = req.delete(url, headers=headers)
        if not response.ok:
            raise LINEOAError(f"delete_card_type_message failed: HTTP {response.status_code}: {response.text}")

    def create_and_send_flex(
        self,
        bot_id: str,
        at_id: str,
        chat_id: str,
        title: str,
        image_url: str,
        tag_name: str = "",
        tag_color: str = "info",
        description: str = "",
        action_label: str = "",
        action_text: str = "",
        delete_after_send: bool = True,
        session=None,
        xsrf_token: str = None,
    ) -> int:
        """
        カードを動的作成 → 送信 → 削除（任意）を一括実行。
        Args:
            bot_id          : Bot ID（U から始まるID）
            at_id           : Bot の @ID（例: "318ogzps"）
            chat_id         : 送信先チャットID
            delete_after_send: 送信後にカードを削除するか（デフォルト True）
        Returns:
            int: 使用した cardTypeMessageId
        """
        card_id = self.create_card_type_message(
            at_id=at_id,
            title=title,
            image_url=image_url,
            tag_name=tag_name,
            tag_color=tag_color,
            description=description,
            action_label=action_label,
            action_text=action_text,
            session=session,
            xsrf_token=xsrf_token,
        )
        lineoa_logger.info(f"create_and_send_flex: created card id={card_id}")
        try:
            self.send_flex_message(
                bot_id=bot_id,
                chat_id=chat_id,
                card_type_message_id=card_id,
                session=session,
                xsrf_token=xsrf_token,
            )
            lineoa_logger.info(f"create_and_send_flex: sent card id={card_id} to {chat_id}")
        finally:
            if delete_after_send:
                try:
                    self.delete_card_type_message(
                        at_id=at_id,
                        card_id=card_id,
                        session=session,
                        xsrf_token=xsrf_token,
                    )
                    lineoa_logger.info(f"create_and_send_flex: deleted card id={card_id}")
                except Exception as e:
                    lineoa_logger.error(f"create_and_send_flex: delete failed (card_id={card_id}): {e}")
        return card_id

    def _handle_response(self, response: requests.Response) -> None:
        if not response.ok:
            raise LINEOAError(f"HTTP {response.status_code}: {response.text}")
