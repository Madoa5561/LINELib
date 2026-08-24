import asyncio
import requests
import aiohttp
import math
import os
import time
import tempfile
import threading
import urllib.parse
from datetime import datetime
import random
import sys
from typing import Optional, Dict, Any, Callable, Generator, Union
from .browser_profile import browser_headers_for_channel
from .exceptions import LINEOAError
from .session_utils import cookie_header, get_stream_cookie_dict, get_xsrf_token
from .sse import SSEParser
from .util import merge_dicts
from .logger import lineoa_logger

class ChatService:
    def __init__(self, request_timeout: float = 30, upload_timeout: float = 120, browser_headers: Optional[Dict[str, str]] = None):
        self.v1_BASE_URL = "https://chat.line.biz/api/v1"
        self.v2_BASE_URL = "https://chat.line.biz/api/v2"
        self.v3_BASE_URL = "https://chat.line.biz/api/v3"
        self.v4_BASE_URL = "https://chat.line.biz/api/v4"
        self.manager_BASE_URL = "https://manager.line.biz/api"
        self.chat_client_version = "20240513144702"
        self.request_timeout = self._positive_finite_timeout(request_timeout, "request_timeout")
        self.upload_timeout = self._positive_finite_timeout(upload_timeout, "upload_timeout")
        self.browser_headers = dict(browser_headers or browser_headers_for_channel("chrome"))
        self._stream_lock = threading.Lock()
        self._active_stream_responses: set[requests.Response] = set()
        self.headers = {
            "Content-Type": "application/json"
        }

    @staticmethod
    def _positive_finite_timeout(value: Any, name: str) -> float:
        try:
            parsed_value = float(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise LINEOAError(f"{name} must be a positive finite number") from error
        if not math.isfinite(parsed_value) or parsed_value <= 0:
            raise LINEOAError(f"{name} must be a positive finite number")
        return parsed_value

    def _base_headers(self) -> Dict[str, str]:
        return {
            **self.browser_headers,
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
        return headers

    def _browser_request_headers(self, **extra: str) -> Dict[str, str]:
        headers = self._base_headers()
        headers.update(extra)
        return headers

    @staticmethod
    def _request(action: str, request_method: Callable[..., requests.Response], *args: Any, **kwargs: Any) -> requests.Response:
        try:
            return request_method(*args, **kwargs)
        except requests.RequestException as error:
            raise LINEOAError(f"{action} failed: {type(error).__name__}") from error

    @staticmethod
    def _cookie_value(cookies: Any) -> str:
        if isinstance(cookies, str):
            return cookies
        if isinstance(cookies, dict):
            return cookie_header(cookies)
        return ""

    @staticmethod
    def _json_response(response: requests.Response, action: str, allow_empty: bool = False) -> Dict[str, Any]:
        if not response.ok:
            raise LINEOAError(f"{action} failed: HTTP {response.status_code}")
        if allow_empty and not response.text:
            return {}
        try:
            payload = response.json()
        except ValueError as error:
            raise LINEOAError(f"{action} failed: invalid JSON response") from error
        if not isinstance(payload, dict):
            raise LINEOAError(f"{action} failed: JSON response must be an object")
        return payload

    @staticmethod
    async def _async_json_response(response: aiohttp.ClientResponse, action: str, allow_empty: bool = False) -> Dict[str, Any]:
        if response.status >= 400:
            raise LINEOAError(f"{action} failed: HTTP {response.status}")
        if allow_empty and response.content_length == 0:
            return {}
        try:
            try:
                payload = await response.json(content_type=None)
            except TypeError:
                payload = await response.json()
        except (ValueError, aiohttp.ContentTypeError) as error:
            raise LINEOAError(f"{action} failed: invalid JSON response") from error
        if not isinstance(payload, dict):
            raise LINEOAError(f"{action} failed: JSON response must be an object")
        return payload

    @staticmethod
    async def _close_owned_async_session(
        session: aiohttp.ClientSession,
        *,
        suppress_errors: bool,
    ) -> None:
        try:
            await session.close()
        except Exception as error:
            if not suppress_errors:
                raise LINEOAError(
                    f"Failed to close internal HTTP session: {type(error).__name__}"
                ) from error
            lineoa_logger.error(
                "Failed to close internal HTTP session after an earlier error: "
                f"{type(error).__name__}"
            )

    def _close_stream(self) -> None:
        """Close all current SSE responses so polling threads can stop promptly."""
        with self._stream_lock:
            responses = tuple(self._active_stream_responses)
        close_error = None
        for response in responses:
            try:
                response.close()
            except Exception as error:
                if close_error is None:
                    close_error = error
        if close_error is not None:
            raise close_error

    def _get_json(self, url: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None, params: Optional[Dict[str, Any]] = None, origin: Optional[str] = None, referer: Optional[str] = None) -> Dict[str, Any]:
        req = session if session else requests
        resp = self._request("GET", req.get, url, headers=self._session_headers(session, xsrf_token=xsrf_token, origin=origin, referer=referer), params=params, timeout=self.request_timeout)
        return self._json_response(resp, f"GET {url}")

    def _put_json(self, url: str, payload: Optional[Dict[str, Any]] = None, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None, origin: Optional[str] = None, referer: Optional[str] = None) -> Dict[str, Any]:
        req = session if session else requests
        resp = self._request("PUT", req.put, url, headers=self._session_headers(session, xsrf_token=xsrf_token, origin=origin, referer=referer), json=payload, timeout=self.request_timeout)
        return self._json_response(resp, f"PUT {url}", allow_empty=True)

    def _post_json(self, url: str, payload: Optional[Dict[str, Any]] = None, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None, origin: Optional[str] = None, referer: Optional[str] = None) -> Dict[str, Any]:
        req = session if session else requests
        resp = self._request("POST", req.post, url, headers=self._session_headers(session, xsrf_token=xsrf_token, origin=origin, referer=referer), json=payload, timeout=self.request_timeout)
        return self._json_response(resp, f"POST {url}", allow_empty=True)

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
        if not os.path.isfile(file_path):
            raise LINEOAError(f"File not found: {file_path}")
        req = session if session else requests
        url_upload = f"https://chat.line.biz/api/v1/bots/{bot_id}/messages/{chat_id}/uploadFile"
        headers_upload = self._browser_request_headers(
            Origin="https://chat.line.biz",
            Referer=f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            **{
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
            },
        )
        if xsrf_token:
            headers_upload["X-XSRF-TOKEN"] = xsrf_token
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "application/octet-stream")}
            resp_upload = self._request("uploadFile", req.post, url_upload, headers=headers_upload, files=files, timeout=self.upload_timeout)
        upload_payload = self._json_response(resp_upload, "uploadFile")
        token = upload_payload.get("contentMessageToken")
        if not token:
            raise LINEOAError("No contentMessageToken returned")
        url_bulk = f"https://chat.line.biz/api/v1/bots/{bot_id}/chats/{chat_id}/messages/bulkSendFiles"
        headers_bulk = self._browser_request_headers(
            Origin="https://chat.line.biz",
            Referer=f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            **{
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
                "Content-Type": "application/json",
            },
        )
        if xsrf_token:
            headers_bulk["x-xsrf-token"] = xsrf_token
        send_id = f"{chat_id}_{int(time.time()*1000)}_{random.randint(1000000,9999999)}"
        payload = {"items": [{"sendId": send_id, "contentMessageToken": token}]}
        resp_bulk = self._request("bulkSendFiles", req.post, url_bulk, headers=headers_bulk, json=payload, timeout=self.request_timeout)
        return self._json_response(resp_bulk, "bulkSendFiles")

    async def async_send_file(self, bot_id: str, chat_id: str, file_path: str, cookies: Optional[Union[Dict[str, str], str]] = None, xsrf_token: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        """
        Async version of send_file using aiohttp.
        """
        url_upload = f"https://chat.line.biz/api/v1/bots/{bot_id}/messages/{chat_id}/uploadFile"
        if not os.path.isfile(file_path):
            raise LINEOAError(f"File not found: {file_path}")
        headers_upload = self._browser_request_headers(
            Origin="https://chat.line.biz",
            Referer=f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
        )
        if xsrf_token:
            headers_upload["X-XSRF-TOKEN"] = xsrf_token
        cookie_value = self._cookie_value(cookies)
        if cookie_value:
            headers_upload["Cookie"] = cookie_value

        own_session = False
        if session is None:
            session = aiohttp.ClientSession()
            own_session = True
        try:
            with open(file_path, "rb") as file_handle:
                data = aiohttp.FormData()
                data.add_field(
                    "file",
                    file_handle,
                    filename=os.path.basename(file_path),
                    content_type="application/octet-stream",
                )
                async with session.post(
                    url_upload,
                    headers=headers_upload,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=self.upload_timeout),
                ) as resp_upload:
                    j = await self._async_json_response(resp_upload, "uploadFile")
            token = j.get('contentMessageToken')
            if not token:
                raise LINEOAError('No contentMessageToken returned')

            url_bulk = f"https://chat.line.biz/api/v1/bots/{bot_id}/chats/{chat_id}/messages/bulkSendFiles"
            headers_bulk = self._browser_request_headers(
                Origin="https://chat.line.biz",
                Referer=f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
                **{"Content-Type": "application/json"},
            )
            if xsrf_token:
                headers_bulk["x-xsrf-token"] = xsrf_token
            if cookie_value:
                headers_bulk["Cookie"] = cookie_value

            send_id = f"{chat_id}_{int(time.time()*1000)}_{random.randint(1000000,9999999)}"
            payload = {"items": [{"sendId": send_id, "contentMessageToken": token}]}
            async with session.post(
                url_bulk,
                headers=headers_bulk,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.request_timeout),
            ) as resp_bulk:
                return await self._async_json_response(resp_bulk, "bulkSendFiles")
        except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as error:
            raise LINEOAError(f"async_send_file failed: {type(error).__name__}") from error
        finally:
            if own_session:
                await self._close_owned_async_session(
                    session,
                    suppress_errors=sys.exc_info()[1] is not None,
                )

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
        if not bot_id or not chat_id:
            raise LINEOAError("bot_id and chat_id are required")
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/chats/{chat_id}/members?limit={limit}"
        headers = self._browser_request_headers(**{
            "accept-language": "ja,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
            "priority": "u=1, i",
            "referer": f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        })
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        req = session if session else requests
        resp = self._request("get_chat_members", req.get, url, headers=headers, timeout=self.request_timeout)
        return self._json_response(resp, "get_chat_members")

    async def async_get_chat_members(self, bot_id: str, chat_id: str, limit: int = 100, cookies: Optional[Union[Dict[str, str], str]] = None, xsrf_token: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        if not bot_id or not chat_id:
            raise LINEOAError("bot_id and chat_id are required")
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/chats/{chat_id}/members?limit={limit}"
        headers = self._base_headers()
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        cookie_value = self._cookie_value(cookies)
        if cookie_value:
            headers["Cookie"] = cookie_value
        own_session = False
        if session is None:
            session = aiohttp.ClientSession()
            own_session = True
        try:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.request_timeout),
            ) as resp:
                return await self._async_json_response(resp, "get_chat_members")
        except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as error:
            raise LINEOAError(f"async_get_chat_members failed: {type(error).__name__}") from error
        finally:
            if own_session:
                await self._close_owned_async_session(
                    session,
                    suppress_errors=sys.exc_info()[1] is not None,
                )

    def listen_messages(self, bot_id: str, chat_id: str, on_message: Optional[Callable[[Dict[str, Any]], None]] = None, session: Optional[requests.Session] = None) -> None:
        """
        Listen for real-time messages in a chat (SSE).
        Args:
            bot_id: Bot ID
            chat_id: Chat ID
            on_message: Callback for new messages
        """
        url = f"https://chat.line.biz/api/v3/bots/{bot_id}/chats/{chat_id}/events"
        headers = self._browser_request_headers(**{
            "accept": "text/event-stream",
            "accept-language": "ja,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
            "priority": "u=1, i",
            "referer": f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        })
        req = session if session else requests
        xsrf_token = get_xsrf_token(session)
        if xsrf_token:
            headers["X-XSRF-TOKEN"] = xsrf_token
        with self._request("listen_messages", req.get, url, headers=headers, stream=True, timeout=(self.request_timeout, 90)) as resp:
            with self._stream_lock:
                self._active_stream_responses.add(resp)
            try:
                if resp.status_code != 200:
                    raise LINEOAError(f"listen_messages failed: HTTP {resp.status_code}")
                try:
                    lines = resp.iter_lines(decode_unicode=True)
                except requests.RequestException as error:
                    raise LINEOAError(
                        f"listen_messages failed: {type(error).__name__}"
                    ) from error
                events = SSEParser.iter_events(lines)
                while True:
                    try:
                        event = next(events)
                    except StopIteration:
                        break
                    except requests.RequestException as error:
                        raise LINEOAError(
                            f"listen_messages failed: {type(error).__name__}"
                        ) from error
                    if event.event not in (None, "chat"):
                        continue
                    data = event.payload
                    if on_message:
                        on_message(data)
                    else:
                        lineoa_logger.info(f"[SSE chat event] {data}")
            finally:
                with self._stream_lock:
                    self._active_stream_responses.discard(resp)

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
        if before is not None and str(before).isdigit():
            params["before"] = int(before)
        if after is not None and str(after).isdigit():
            params["after"] = int(after)
        headers = self._browser_request_headers(**{
            "accept-language": "ja,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
            "priority": "u=1, i",
            "referer": f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        })
        req = session if session else requests
        xsrf_cookie = get_xsrf_token(session)
        if xsrf_token:
            headers["X-XSRF-TOKEN"] = xsrf_token
        elif xsrf_cookie:
            headers["X-XSRF-TOKEN"] = xsrf_cookie
        else:
            csrf_resp = self._request("get_csrf_token", req.get, "https://chat.line.biz/api/v1/csrfToken", headers=headers, timeout=self.request_timeout)
            csrf_json = self._json_response(csrf_resp, "get_csrf_token")
            token = csrf_json.get("token")
            if not isinstance(token, str) or not token:
                raise LINEOAError("get_csrf_token failed: response did not contain a token")
            headers["X-XSRF-TOKEN"] = token
        resp = self._request("get_chat_messages", req.get, url, headers=headers, params=params, timeout=self.request_timeout)
        return self._json_response(resp, "get_chat_messages")

    async def async_get_chat_messages(self, bot_id: str, chat_id: str, cookies: Optional[Union[Dict[str, str], str]] = None, xsrf_token: Optional[str] = None, limit: int = 50, before: Optional[str] = None, after: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        url = f"{self.v3_BASE_URL}/bots/{bot_id}/chats/{chat_id}/messages"
        params = {"limit": int(limit)}
        if before is not None and str(before).isdigit():
            params["before"] = int(before)
        if after is not None and str(after).isdigit():
            params["after"] = int(after)
        headers = self._base_headers()
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        cookie_value = self._cookie_value(cookies)
        if cookie_value:
            headers["Cookie"] = cookie_value
        own_session = False
        if session is None:
            session = aiohttp.ClientSession()
            own_session = True
        try:
            async with session.get(
                url,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=self.request_timeout),
            ) as resp:
                return await self._async_json_response(resp, "get_chat_messages")
        except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as error:
            raise LINEOAError(f"async_get_chat_messages failed: {type(error).__name__}") from error
        finally:
            if own_session:
                await self._close_owned_async_session(
                    session,
                    suppress_errors=sys.exc_info()[1] is not None,
                )

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
        url = f"https://chat.line.biz/api/v2/bots/{bot_id}/chats"
        params = {
            "folderType": folder_type,
            "tagIds": tag_ids,
            "autoTagIds": auto_tag_ids,
            "limit": limit,
            "prioritizePinnedChat": str(prioritize_pinned_chat).lower(),
        }
        headers = self._browser_request_headers(**{
            "accept-language": "ja,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
            "priority": "u=1, i",
            "referer": f"https://chat.line.biz/{bot_id}",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        })
        req = session if session else requests
        xsrf_cookie = get_xsrf_token(session)
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        elif xsrf_cookie:
            headers["x-xsrf-token"] = xsrf_cookie
        else:
            csrf_resp = self._request("get_csrf_token", req.get, "https://chat.line.biz/api/v1/csrfToken", headers=headers, timeout=self.request_timeout)
            csrf_json = self._json_response(csrf_resp, "get_csrf_token")
            token = csrf_json.get("token")
            if not isinstance(token, str) or not token:
                raise LINEOAError("get_csrf_token failed: response did not contain a token")
            headers["x-xsrf-token"] = token
        resp = self._request("get_chats", req.get, url, headers=headers, params=params, timeout=self.request_timeout)
        return self._json_response(resp, "get_chats")

    def get_me(self, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Get own account info.
        Returns:
            dict: Account info
        """
        return self._get_json("https://chat.line.biz/api/v1/me", session=session, xsrf_token=xsrf_token)

    def get_bot_account(self, bot_id: str, no_filter: bool = True, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
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
        return self._get_json(url, session=session, xsrf_token=xsrf_token, params=params)

    def get_csrf_token(self, session: Optional[requests.Session] = None) -> Dict[str, Any]:
        """
        Get CSRF token.
        Returns:
            dict: CSRF token info
        """
        return self._get_json("https://chat.line.biz/api/v1/csrfToken", session=session)

    def get_whitelist_domains(self, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json("https://chat.line.biz/api/v1/whitelistDomains", session=session, xsrf_token=xsrf_token)

    def get_me_settings_pc(self, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        return self._get_json("https://chat.line.biz/api/v1/me/settings/pc", session=session, xsrf_token=xsrf_token)

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
        url = "https://chat.line.biz/api/v1/bots"
        params = {"limit": limit, "noFilter": str(no_filter).lower()}
        browser_headers = self._base_headers()
        if xsrf_token:
            browser_headers["x-xsrf-token"] = xsrf_token
        req = session if session else requests
        resp = self._request("get_bot_accounts", req.get, url, headers=browser_headers, params=params, timeout=self.request_timeout)
        return self._json_response(resp, "get_bot_accounts")

    def get_pinned_messages(self, bot_id: str, chat_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Get pinned messages in a chat.
        Args:
            bot_id: Bot ID
            chat_id: Chat ID
        Returns:
            dict: Pinned messages
        """
        url = f"{self.v2_BASE_URL}/bots/{bot_id}/chats/{chat_id}/messages/pin"
        return self._get_json(url, session=session, xsrf_token=xsrf_token)

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
        resp = self._request(
            "get_content_preview",
            req.get,
            url,
            headers=self._browser_request_headers(**{
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            }),
            timeout=self.request_timeout,
        )
        if not resp.ok:
            raise LINEOAError(f"get_content_preview failed: HTTP {resp.status_code}")
        return resp.content

    def get_sticker_image(self, sticker_id: str, session: Optional[requests.Session] = None) -> bytes:
        url = f"https://stickershop.line-scdn.net/stickershop/v1/sticker/{sticker_id}/android/sticker.png"
        req = session if session else requests
        resp = self._request(
            "get_sticker_image",
            req.get,
            url,
            headers=self._browser_request_headers(**{
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            }),
            timeout=self.request_timeout,
        )
        if not resp.ok:
            raise LINEOAError(f"get_sticker_image failed: HTTP {resp.status_code}")
        return resp.content

    def _download_to_file(self, url: str, file_path: str, session: Optional[requests.Session], action: str) -> str:
        req = session if session else requests
        target_path = os.path.abspath(file_path)
        parent = os.path.dirname(target_path)
        os.makedirs(parent, exist_ok=True)
        descriptor, temporary_path = tempfile.mkstemp(
            dir=parent,
            prefix=f".{os.path.basename(file_path)}.",
            suffix=".tmp",
        )
        try:
            with self._request(
                action,
                req.get,
                url,
                headers=self._browser_request_headers(**{
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                }),
                stream=True,
                timeout=self.request_timeout,
            ) as response:
                if not response.ok:
                    raise LINEOAError(f"{action} failed: HTTP {response.status_code}")
                with os.fdopen(descriptor, "wb") as file:
                    descriptor = -1
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            file.write(chunk)
                    file.flush()
                    os.fsync(file.fileno())
            os.replace(temporary_path, target_path)
        except Exception as error:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
            if isinstance(error, requests.RequestException):
                raise LINEOAError(
                    f"{action} failed: {type(error).__name__}"
                ) from error
            raise
        return file_path

    def save_sticker_image(self, sticker_id: str, file_path: str, session: Optional[requests.Session] = None) -> str:
        url = f"https://stickershop.line-scdn.net/stickershop/v1/sticker/{sticker_id}/android/sticker.png"
        return self._download_to_file(url, file_path, session, "save_sticker_image")

    def save_content_preview(self, bot_id: str, content_hash: str, file_path: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> str:
        url = f"https://chat-content.line.biz/bot/{bot_id}/{content_hash}/preview"
        return self._download_to_file(url, file_path, session, "save_content_preview")

    def set_typing(self, bot_id: str, chat_id: str, session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Send typing indicator to chat.
        Args:
            bot_id: Bot ID
            chat_id: Chat ID
        Returns:
            dict: Always empty
        """
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/chats/{chat_id}/typing"
        return self._put_json(
            url,
            session=session,
            xsrf_token=xsrf_token,
            origin="https://chat.line.biz",
            referer=f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
        )

    def streaming_state(self, bot_id: str, state: Dict[str, Any], session: Optional[requests.Session] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
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
        return self._put_json(
            url,
            payload=payload,
            session=session,
            xsrf_token=xsrf_token,
            origin="https://chat.line.biz",
            referer=f"https://chat.line.biz/{bot_id}/chat/",
        )

    def get_streaming_api_token(self, bot_id: str, session: Optional[object] = None, xsrf_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Get streaming API token for bot.
        Args:
            bot_id: Bot ID
        Returns:
            dict: API response
        """
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/streamingApiToken"
        headers = self._browser_request_headers(
            Origin="https://chat.line.biz",
            Referer=f"https://chat.line.biz/{bot_id}/chat/",
        )
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        req = session if session else requests
        try:
            response = self._request("get_streaming_api_token", req.post, url, headers=headers, data="", timeout=self.request_timeout)
            payload = self._json_response(response, "get_streaming_api_token")
            if "streamingApiBaseUrl" not in payload:
                payload["streamingApiBaseUrl"] = "https://chat-streaming-api.line.biz"
            if "streamingApiVersion" not in payload:
                payload["streamingApiVersion"] = "v2"
            return payload
        except LINEOAError:
            raise
        except requests.RequestException as error:
            raise LINEOAError(f"get_streaming_api_token failed: {error}") from error

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
        try:
            ping_secs = int(ping_secs)
            max_stream_seconds = float(max_stream_seconds)
        except (TypeError, ValueError, OverflowError) as error:
            raise LINEOAError("Invalid LINE streaming timing configuration") from error
        if ping_secs < 1 or not math.isfinite(max_stream_seconds) or max_stream_seconds <= 0:
            raise LINEOAError("Invalid LINE streaming timing configuration")

        parsed_base_url = urllib.parse.urlparse(base_url)
        if (
            parsed_base_url.scheme != "https"
            or parsed_base_url.hostname != "chat-streaming-api.line.biz"
            or parsed_base_url.port is not None
            or parsed_base_url.username is not None
            or parsed_base_url.password is not None
            or parsed_base_url.path not in {"", "/"}
            or parsed_base_url.query
            or parsed_base_url.fragment
        ):
            raise LINEOAError("Invalid LINE streaming API base URL")
        if not isinstance(version, str) or not version.startswith("v") or not version[1:].isdigit():
            raise LINEOAError("Invalid LINE streaming API version")
        stream_url = f"https://chat-streaming-api.line.biz/api/{version}/sse"
        params = {
            "token": streaming_api_token,
            "deviceType": device_type,
            "clientType": client_type,
            "pingSecs": ping_secs
        }
        if last_event_id:
            params["lastEventId"] = last_event_id
        headers = self._browser_request_headers(**{
            "accept": "text/event-stream",
            "accept-language": "ja,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
            "cache-control": "no-cache",
            "origin": "https://chat.line.biz",
            "referer": "https://chat.line.biz/",
            "priority": "u=1, i",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
        })
        if xsrf_token:
            headers["X-XSRF-TOKEN"] = xsrf_token
        if session:
            stream_cookies = get_stream_cookie_dict(session)
            if stream_cookies:
                headers["cookie"] = cookie_header(stream_cookies)
            req = session
        else:
            req = requests
        started_at = time.monotonic()
        stream_timeout = (
            min(self.request_timeout, max_stream_seconds),
            max(90, ping_secs + 30),
        )
        with self._request("stream_events", req.get, stream_url, headers=headers, params=params, stream=True, timeout=stream_timeout) as resp:
            with self._stream_lock:
                self._active_stream_responses.add(resp)
            deadline_reached = threading.Event()

            def close_at_deadline() -> None:
                deadline_reached.set()
                try:
                    resp.close()
                except Exception:
                    return

            remaining_stream_seconds = max_stream_seconds - (time.monotonic() - started_at)
            deadline_timer = threading.Timer(max(0, remaining_stream_seconds), close_at_deadline)
            deadline_timer.daemon = True
            deadline_timer.start()
            try:
                if not resp.ok:
                    raise LINEOAError(f"stream_events failed: HTTP {resp.status_code}")
                events = SSEParser.iter_events(resp.iter_lines(decode_unicode=True))
                for event in events:
                    if time.monotonic() - started_at >= max_stream_seconds:
                        break
                    yield {
                        "id": event.id,
                        "type": event.event,
                        "payload": event.payload,
                        "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                    }
            except requests.RequestException as error:
                if not deadline_reached.is_set():
                    raise LINEOAError(
                        f"stream_events failed: {type(error).__name__}"
                    ) from error
            finally:
                deadline_timer.cancel()
                with self._stream_lock:
                    self._active_stream_responses.discard(resp)

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
        browser_headers = self._browser_request_headers(
            Referer=f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            Origin="https://chat.line.biz",
            **{
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
                "Content-Type": "application/json",
            },
        )
        if xsrf_token:
            browser_headers["x-xsrf-token"] = xsrf_token
        req = session if session else requests
        response = self._request("send_message", req.post, url, headers=browser_headers, json=message, timeout=self.request_timeout)
        if not response.ok:
            raise LINEOAError(f"send_message failed: HTTP {response.status_code}")
        return {}

    async def async_send_message(self, bot_id: str, chat_id: str, message: Dict[str, Any], cookies: Optional[Union[Dict[str, str], str]] = None, xsrf_token: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        """
        Async version of send_message using aiohttp.
        cookies: dict of cookie name->value to send in Cookie header.
        """
        url = f"{self.v1_BASE_URL}/bots/{bot_id}/chats/{chat_id}/messages/send"
        headers = self._browser_request_headers(
            Referer=f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            Origin="https://chat.line.biz",
            **{
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                "Content-Type": "application/json",
            },
        )
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        cookie_value = self._cookie_value(cookies)
        if cookie_value:
            headers["Cookie"] = cookie_value

        own_session = False
        if session is None:
            session = aiohttp.ClientSession()
            own_session = True
        try:
            async with session.post(
                url,
                headers=headers,
                json=message,
                timeout=aiohttp.ClientTimeout(total=self.request_timeout),
            ) as resp:
                if resp.status >= 400:
                    raise LINEOAError(f"async_send_message failed: HTTP {resp.status}")
        except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as error:
            raise LINEOAError(f"async_send_message failed: {type(error).__name__}") from error
        finally:
            if own_session:
                await self._close_owned_async_session(
                    session,
                    suppress_errors=sys.exc_info()[1] is not None,
                )
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
        browser_headers = self._browser_request_headers(
            Origin="https://chat.line.biz",
            Referer=f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            **{
                "Content-Type": "application/json",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
            },
        )
        if xsrf_token:
            browser_headers["x-xsrf-token"] = xsrf_token
        req = session if session else requests
        response = self._request("send_flex_message", req.post, url, headers=browser_headers, json=payload, timeout=self.request_timeout)
        if not response.ok:
            raise LINEOAError(f"send_flex_message failed: HTTP {response.status_code}")
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
        headers = self._browser_request_headers(
            Origin="https://chat.line.biz",
            Referer=f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
        )
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        req = session if session else requests
        response = self._request("get_flex_json", req.get, url, headers=headers, params=params, timeout=self.request_timeout)
        return self._json_response(response, "get_flex_json")

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
        browser_headers = self._browser_request_headers(
            Origin="https://chat.line.biz",
            Referer=f"https://chat.line.biz/{bot_id}/chat/{chat_id}",
            **{
                "Content-Type": "application/json",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
            },
        )
        if xsrf_token:
            browser_headers["x-xsrf-token"] = xsrf_token
        req = session if session else requests
        response = self._request("mark_as_read", req.put, url, headers=browser_headers, json=payload, timeout=self.request_timeout)
        if not response.ok:
            raise LINEOAError(f"mark_as_read failed: HTTP {response.status_code}")
        return {}


    def _manager_headers(self, session, at_id: str, xsrf_token=None) -> dict:
        """manager.line.biz 用ヘッダー生成"""
        h = self._browser_request_headers(
            Origin="https://manager.line.biz",
            Referer="https://manager.line.biz/",
            **{"Content-Type": "application/json"},
        )
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
        response = self._request("create_card_type_message", req.post, url, headers=headers, json=payload, timeout=self.request_timeout)
        response_payload = self._json_response(response, "create_card_type_message")
        card_id = response_payload.get("id")
        if not card_id:
            raise LINEOAError("create_card_type_message failed: response did not contain an id")
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
        response = self._request("delete_card_type_message", req.delete, url, headers=headers, timeout=self.request_timeout)
        if not response.ok:
            raise LINEOAError(f"delete_card_type_message failed: HTTP {response.status_code}")

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
            raise LINEOAError(f"HTTP {response.status_code}")
