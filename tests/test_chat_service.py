import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests


chat_service_module = importlib.import_module("LINELib.ChatService")
ChatService = chat_service_module.ChatService


class SyncResponse:
    def __init__(self, payload=None):
        self.ok = True
        self.status_code = 200
        self.text = "" if payload is None else "json"
        self._payload = payload or {}

    def json(self):
        return self._payload


class AsyncResponse:
    def __init__(self, payload):
        self.status = 200
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def text(self):
        return "json"

    async def json(self):
        return self._payload


class FakeAioSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if len(self.calls) == 1:
            return AsyncResponse({"contentMessageToken": "content-token"})
        return AsyncResponse({"ok": True})


class FakeFormData:
    latest = None

    def __init__(self):
        self.file_handle = None
        FakeFormData.latest = self

    def add_field(self, name, value, **kwargs):
        self.file_handle = value


class ChatServiceTests(unittest.TestCase):
    def test_streaming_state_uses_authenticated_session(self):
        service = ChatService()
        session = requests.Session()
        session.cookies.set("chat-session", "secret", domain="chat.line.biz")
        session.put = Mock(return_value=SyncResponse())

        result = service.streaming_state(
            "Ubot",
            {"connectionId": "connection", "idle": True},
            session=session,
            xsrf_token="xsrf",
        )

        self.assertEqual({}, result)
        _, kwargs = session.put.call_args
        self.assertEqual("xsrf", kwargs["headers"]["x-xsrf-token"])
        self.assertIn("chat-session=secret", kwargs["headers"]["Cookie"])
        self.assertEqual(30, kwargs["timeout"])

    def test_get_me_uses_authenticated_session(self):
        service = ChatService()
        session = requests.Session()
        session.get = Mock(return_value=SyncResponse({"name": "owner"}))

        result = service.get_me(session=session, xsrf_token="xsrf")

        self.assertEqual({"name": "owner"}, result)
        _, kwargs = session.get.call_args
        self.assertEqual("xsrf", kwargs["headers"]["x-xsrf-token"])

    def test_get_chats_fetches_csrf_with_same_session(self):
        service = ChatService(request_timeout=12)
        session = requests.Session()
        session.get = Mock(
            side_effect=[
                SyncResponse({"token": "fresh-xsrf"}),
                SyncResponse({"list": []}),
            ]
        )

        result = service.get_chats("Ubot", session=session)

        self.assertEqual({"list": []}, result)
        first_url = session.get.call_args_list[0].args[0]
        second_kwargs = session.get.call_args_list[1].kwargs
        self.assertEqual("https://chat.line.biz/api/v1/csrfToken", first_url)
        self.assertEqual("fresh-xsrf", second_kwargs["headers"]["x-xsrf-token"])
        self.assertEqual(12, second_kwargs["timeout"])


class AsyncChatServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_send_file_closes_file_handle(self):
        service = ChatService()
        session = FakeAioSession()
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "upload.bin"
            file_path.write_bytes(b"payload")
            with patch.object(chat_service_module.aiohttp, "FormData", FakeFormData):
                result = await service.async_send_file(
                    "Ubot",
                    "Uchat",
                    str(file_path),
                    session=session,
                )

        self.assertEqual({"ok": True}, result)
        self.assertTrue(FakeFormData.latest.file_handle.closed)


if __name__ == "__main__":
    unittest.main()
