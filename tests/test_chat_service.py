import importlib
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import requests

from LINELib.exceptions import LINEOAError


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

    async def json(self, **kwargs):
        return self._payload


class StreamResponse(SyncResponse):
    def __init__(self, payload=None, chunks=()):
        super().__init__(payload)
        self.chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def iter_lines(self, decode_unicode=True):
        return iter(())

    def iter_content(self, chunk_size):
        return iter(self.chunks)

    def close(self):
        return None


class DeadlineStreamResponse(StreamResponse):
    def __init__(self):
        super().__init__()
        self.closed = threading.Event()

    def iter_lines(self, decode_unicode=True):
        self.closed.wait(1)
        if False:
            yield None
        raise requests.ConnectionError("stream closed")

    def close(self):
        self.closed.set()


class FailingStreamResponse(StreamResponse):
    def iter_lines(self, decode_unicode=True):
        raise requests.ConnectionError("stream lost")


class ByteStreamResponse(StreamResponse):
    def iter_lines(self, decode_unicode=True):
        return iter(
            [
                b"id: 1",
                b"event: chat",
                b'data: {"sequence": 1}',
                b"",
                b"event: chat",
                b'data: {"sequence": 2}',
                b"",
            ]
        )


class InterruptedDownloadResponse(StreamResponse):
    def iter_content(self, chunk_size):
        yield b"partial"
        raise requests.ConnectionError("download interrupted")


class LegacyAsyncioTimeoutError(Exception):
    pass


class RaisingAsyncContext:
    async def __aenter__(self):
        raise LegacyAsyncioTimeoutError("request timed out")

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeAioSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if len(self.calls) == 1:
            return AsyncResponse({"contentMessageToken": "content-token"})
        return AsyncResponse({"ok": True})

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return AsyncResponse({"list": []})


class FakeFormData:
    latest = None

    def __init__(self):
        self.file_handle = None
        FakeFormData.latest = self

    def add_field(self, name, value, **kwargs):
        self.file_handle = value


class ChatServiceTests(unittest.TestCase):
    def test_send_operations_reject_missing_ids_before_request(self):
        service = ChatService()
        session = Mock()
        operations = (
            lambda: service.send_message("", "Uchat", {}, session=session),
            lambda: service.send_mention("Ubot", "Uchat", "", session=session),
            lambda: service.send_flex_message("Ubot", "", 1, session=session),
            lambda: service.send_file("Ubot", "Uchat", None, session=session),
            lambda: service.create_card_type_message(
                "@",
                "title",
                "https://example.com/image.png",
                session=session,
            ),
        )

        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(LINEOAError, "required"):
                    operation()

        session.post.assert_not_called()

    def test_create_card_type_message_wraps_invalid_response_id(self):
        service = ChatService()
        session = Mock()
        for invalid_id in ("not-a-number", 1.5, True, -1):
            with self.subTest(invalid_id=invalid_id):
                session.post.return_value = SyncResponse({"id": invalid_id})
                with self.assertRaisesRegex(LINEOAError, "response id is invalid"):
                    service.create_card_type_message(
                        "@bot",
                        "title",
                        "https://example.com/image.png",
                        session=session,
                    )

    def test_flex_operations_reject_invalid_ids_before_request(self):
        service = ChatService()
        session = Mock()
        operations = (
            lambda: service.get_flex_json(None, "Uchat", "message", session=session),
            lambda: service.get_flex_json(
                "Ubot",
                "Uchat",
                "message",
                timestamp=0,
                session=session,
            ),
            lambda: service.mark_as_read("Ubot", "Uchat", None, session=session),
            lambda: service.mark_as_read(
                "Ubot",
                "Uchat",
                "message",
                timestamp=float("nan"),
                session=session,
            ),
            lambda: service.send_flex_message(
                "Ubot",
                "Uchat",
                True,
                session=session,
            ),
            lambda: service.delete_card_type_message(None, 1, session=session),
            lambda: service.delete_card_type_message("@bot", 0, session=session),
        )

        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaises(LINEOAError):
                    operation()

        session.get.assert_not_called()
        session.put.assert_not_called()
        session.post.assert_not_called()
        session.delete.assert_not_called()

    def test_create_and_send_flex_reports_cleanup_failure_after_success(self):
        service = ChatService()
        cleanup_error = LINEOAError("delete failed")
        service.create_card_type_message = Mock(return_value=123)
        service.send_flex_message = Mock(return_value={})
        service.delete_card_type_message = Mock(side_effect=cleanup_error)

        with self.assertRaises(LINEOAError) as raised:
            service.create_and_send_flex(
                "Ubot",
                "@bot",
                "Uchat",
                "title",
                "https://example.com/image.png",
            )

        self.assertEqual("flex_cleanup_failed", raised.exception.code)
        self.assertEqual(
            {"card_id": 123, "message_sent": True},
            raised.exception.details,
        )
        self.assertIs(cleanup_error, raised.exception.__cause__)

    def test_create_and_send_flex_preserves_send_failure_when_cleanup_fails(self):
        service = ChatService()
        send_error = LINEOAError("send failed")
        service.create_card_type_message = Mock(return_value=123)
        service.send_flex_message = Mock(side_effect=send_error)
        service.delete_card_type_message = Mock(side_effect=LINEOAError("delete failed"))

        with self.assertRaises(LINEOAError) as raised:
            service.create_and_send_flex(
                "Ubot",
                "@bot",
                "Uchat",
                "title",
                "https://example.com/image.png",
            )

        self.assertIs(send_error, raised.exception)

    def test_create_and_send_flex_rejects_non_boolean_cleanup_option(self):
        service = ChatService()
        service.create_card_type_message = Mock()

        with self.assertRaisesRegex(LINEOAError, "boolean"):
            service.create_and_send_flex(
                "Ubot",
                "@bot",
                "Uchat",
                "title",
                "https://example.com/image.png",
                delete_after_send="false",
            )

        service.create_card_type_message.assert_not_called()

    def test_constructor_rejects_non_finite_timeouts(self):
        invalid_options = (
            {"request_timeout": float("nan")},
            {"request_timeout": float("inf")},
            {"upload_timeout": 0},
            {"upload_timeout": "invalid"},
        )

        for options in invalid_options:
            with self.subTest(options=options):
                with self.assertRaises(LINEOAError):
                    ChatService(**options)

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
        self.assertNotIn("Cookie", kwargs["headers"])
        self.assertEqual("secret", session.cookies.get("chat-session", domain="chat.line.biz"))
        self.assertEqual(30, kwargs["timeout"])

    def test_streaming_operations_reject_missing_ids_before_request(self):
        service = ChatService()
        session = requests.Session()
        session.get = Mock(return_value=StreamResponse())
        session.post = Mock(return_value=SyncResponse({"streamingApiToken": "token"}))
        session.put = Mock(return_value=SyncResponse())
        operations = (
            lambda: service.get_streaming_api_token("", session=session),
            lambda: service.streaming_state(
                "",
                {"connectionId": "connection", "idle": True},
                session=session,
            ),
            lambda: service.set_typing("Ubot", "", session=session),
            lambda: next(service.stream_events(None, session=session)),
        )

        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(LINEOAError, "required"):
                    operation()

        session.get.assert_not_called()
        session.post.assert_not_called()
        session.put.assert_not_called()

    def test_send_message_uses_injected_edge_profile(self):
        browser_headers = {
            "User-Agent": "edge-user-agent",
            "sec-ch-ua": "edge-client-hint",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
        service = ChatService(browser_headers=browser_headers)
        session = requests.Session()
        session.cookies.set("chat-session", "secret", domain="chat.line.biz")
        session.post = Mock(return_value=SyncResponse())

        service.send_message("Ubot", "Uchat", {"type": "text"}, session=session)

        _, kwargs = session.post.call_args
        self.assertEqual("edge-user-agent", kwargs["headers"]["User-Agent"])
        self.assertEqual("edge-client-hint", kwargs["headers"]["sec-ch-ua"])
        self.assertNotIn("Cookie", kwargs["headers"])

    def test_stream_events_rejects_untrusted_base_url(self):
        service = ChatService()
        invalid_base_urls = (
            "https://example.com",
            "https://chat-streaming-api.line.biz:invalid",
            None,
        )

        for base_url in invalid_base_urls:
            with self.subTest(base_url=base_url):
                events = service.stream_events("token", base_url=base_url)
                with self.assertRaisesRegex(LINEOAError, "Invalid LINE streaming"):
                    next(events)

    def test_stream_events_rejects_non_finite_timing_values(self):
        invalid_options = (
            {"ping_secs": float("inf")},
            {"ping_secs": True},
            {"ping_secs": 1.5},
            {"max_stream_seconds": float("nan")},
            {"max_stream_seconds": float("inf")},
            {"max_stream_seconds": True},
        )

        for options in invalid_options:
            with self.subTest(options=options):
                session = requests.Session()
                session.get = Mock(return_value=StreamResponse())
                events = ChatService().stream_events("token", session=session, **options)

                with self.assertRaises(LINEOAError):
                    next(events)

                session.get.assert_not_called()

    def test_stream_disconnect_is_wrapped_as_library_error(self):
        session = requests.Session()
        session.get = Mock(return_value=FailingStreamResponse())

        with self.assertRaises(LINEOAError) as raised:
            list(ChatService().stream_events("token", session=session, max_stream_seconds=1))

        self.assertIsInstance(raised.exception.__cause__, requests.ConnectionError)

    def test_stream_events_decode_bytes_and_preserve_event_id(self):
        session = requests.Session()
        session.get = Mock(return_value=ByteStreamResponse())

        events = list(
            ChatService().stream_events(
                "token",
                session=session,
                max_stream_seconds=1,
            )
        )

        self.assertEqual(["1", "1"], [event["id"] for event in events])
        self.assertEqual([1, 2], [event["payload"]["sequence"] for event in events])

    def test_listen_messages_disconnect_is_wrapped_as_library_error(self):
        session = requests.Session()
        session.get = Mock(return_value=FailingStreamResponse())

        with self.assertRaises(LINEOAError) as raised:
            ChatService().listen_messages("Ubot", "Uchat", session=session)

        self.assertIsInstance(raised.exception.__cause__, requests.ConnectionError)

    def test_get_chat_members_rejects_missing_ids_before_request(self):
        service = ChatService()
        session = requests.Session()
        session.get = Mock(return_value=SyncResponse({"list": []}))

        for bot_id, chat_id in ((None, "Uchat"), ("Ubot", None), ("", "Uchat")):
            with self.subTest(bot_id=bot_id, chat_id=chat_id):
                with self.assertRaisesRegex(LINEOAError, "required"):
                    service.get_chat_members(bot_id, chat_id, session=session)

        session.get.assert_not_called()

    def test_history_and_members_reject_invalid_queries_before_request(self):
        service = ChatService()
        session = requests.Session()
        session.get = Mock(return_value=SyncResponse({"list": []}))
        operations = (
            lambda: service.get_chat_messages(
                "Ubot",
                "Uchat",
                limit=0,
                session=session,
                xsrf_token="xsrf",
            ),
            lambda: service.get_chat_messages(
                "Ubot",
                "Uchat",
                limit=101,
                session=session,
                xsrf_token="xsrf",
            ),
            lambda: service.get_chat_messages(
                "Ubot",
                "Uchat",
                before="",
                session=session,
                xsrf_token="xsrf",
            ),
            lambda: service.get_chat_messages(
                "Ubot",
                "Uchat",
                after=0,
                session=session,
                xsrf_token="xsrf",
            ),
            lambda: service.get_chat_members(
                "Ubot",
                "Uchat",
                limit="1&extra=true",
                session=session,
            ),
            lambda: service.listen_messages(None, "Uchat", session=session),
        )

        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaises(LINEOAError):
                    operation()

        session.get.assert_not_called()

    def test_history_and_members_normalize_valid_queries(self):
        service = ChatService()
        session = requests.Session()
        session.get = Mock(return_value=SyncResponse({"list": []}))
        opaque_cursor = "opaque-cursor-token"

        service.get_chat_messages(
            "Ubot",
            "Uchat",
            limit="100",
            before=opaque_cursor,
            session=session,
            xsrf_token="xsrf",
        )

        _, history_kwargs = session.get.call_args
        self.assertEqual(
            {"limit": 100, "before": opaque_cursor},
            history_kwargs["params"],
        )

        service.get_chat_members("Ubot", "Uchat", limit="100", session=session)

        members_url, members_kwargs = session.get.call_args
        self.assertNotIn("?", members_url)
        self.assertEqual({"limit": 100}, members_kwargs["params"])

    def test_stream_events_only_forwards_chat_domain_cookies(self):
        service = ChatService()
        session = requests.Session()
        session.cookies.set("__Host-chat-ses", "chat-value", domain="chat.line.biz")
        session.cookies.set("XSRF-TOKEN", "chat-xsrf", domain="chat.line.biz")
        session.cookies.set("XSRF-TOKEN", "manager-xsrf", domain="manager.line.biz")
        session.get = Mock(return_value=StreamResponse())

        list(service.stream_events("token", session=session))

        _, kwargs = session.get.call_args
        self.assertIn("__Host-chat-ses=chat-value", kwargs["headers"]["cookie"])
        self.assertIn("XSRF-TOKEN=chat-xsrf", kwargs["headers"]["cookie"])
        self.assertNotIn("manager-xsrf", kwargs["headers"]["cookie"])
        self.assertNotIn("accept-encoding", kwargs["headers"])

    def test_stream_events_closes_response_at_max_duration(self):
        service = ChatService()
        session = requests.Session()
        response = DeadlineStreamResponse()
        session.get = Mock(return_value=response)

        started_at = time.monotonic()
        events = list(service.stream_events("token", session=session, max_stream_seconds=0.02))

        self.assertEqual([], events)
        self.assertTrue(response.closed.is_set())
        self.assertLess(time.monotonic() - started_at, 0.5)
        _, kwargs = session.get.call_args
        self.assertEqual(0.02, kwargs["timeout"][0])

    def test_close_stream_closes_all_active_responses(self):
        service = ChatService()
        first_response = Mock()
        second_response = Mock()
        service._active_stream_responses.update({first_response, second_response})

        service._close_stream()

        first_response.close.assert_called_once_with()
        second_response.close.assert_called_once_with()

    def test_invalid_json_is_wrapped_as_library_error(self):
        service = ChatService()
        response = SyncResponse()
        response.text = "not-json"
        response.json = Mock(side_effect=ValueError("bad json"))
        session = requests.Session()
        session.get = Mock(return_value=response)

        with self.assertRaisesRegex(Exception, "invalid JSON response"):
            service.get_me(session=session)

    def test_sticker_save_streams_to_target_file(self):
        service = ChatService()
        session = requests.Session()
        session.get = Mock(return_value=StreamResponse(chunks=(b"first", b"second")))

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "nested" / "sticker.png"
            result = service.save_sticker_image("123", str(target), session=session)

            self.assertEqual(b"firstsecond", target.read_bytes())

        self.assertEqual(str(target), result)
        _, kwargs = session.get.call_args
        self.assertTrue(kwargs["stream"])

    def test_download_disconnect_is_wrapped_and_partial_file_is_removed(self):
        service = ChatService()
        session = requests.Session()
        session.get = Mock(return_value=InterruptedDownloadResponse())

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "media.bin"
            with self.assertRaises(LINEOAError) as raised:
                service.save_content_preview(
                    "Ubot",
                    "content-hash",
                    str(target),
                    session=session,
                )

            self.assertFalse(target.exists())
            self.assertEqual([], list(Path(temp_dir).glob("*.tmp")))

        self.assertIsInstance(raised.exception.__cause__, requests.ConnectionError)

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
        self.assertEqual(25, second_kwargs["params"]["limit"])
        self.assertEqual(12, second_kwargs["timeout"])

    def test_get_chats_rejects_limits_outside_api_range_before_request(self):
        service = ChatService()
        session = requests.Session()
        session.get = Mock(return_value=SyncResponse({"list": []}))

        for limit in (True, 0, 26, 1.5, "invalid"):
            with self.subTest(limit=limit):
                with self.assertRaisesRegex(LINEOAError, "between 1 and 25"):
                    service.get_chats("Ubot", limit=limit, session=session)

        session.get.assert_not_called()

    def test_get_chat_messages_stops_when_csrf_request_fails(self):
        service = ChatService()
        csrf_failure = SyncResponse()
        csrf_failure.ok = False
        csrf_failure.status_code = 503
        session = requests.Session()
        session.get = Mock(
            side_effect=[csrf_failure, SyncResponse({"list": []})]
        )

        with self.assertRaisesRegex(LINEOAError, "HTTP 503"):
            service.get_chat_messages("Ubot", "Uchat", session=session)

        self.assertEqual(1, session.get.call_count)


class AsyncChatServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_send_operations_reject_missing_ids_before_request(self):
        service = ChatService()
        session = FakeAioSession()

        with self.assertRaisesRegex(LINEOAError, "required"):
            await service.async_send_message("Ubot", "", {}, session=session)
        with self.assertRaisesRegex(LINEOAError, "required"):
            await service.async_send_file("", "Uchat", "missing.bin", session=session)
        with self.assertRaisesRegex(LINEOAError, "file_path"):
            await service.async_send_file("Ubot", "Uchat", None, session=session)

        self.assertEqual([], session.calls)

    async def test_session_close_error_does_not_mask_request_failure(self):
        service = ChatService()
        session = Mock()

        class ConnectionFailureContext:
            async def __aenter__(self):
                raise chat_service_module.aiohttp.ClientConnectionError(
                    "request failed"
                )

            async def __aexit__(self, exc_type, exc, traceback):
                return False

        session.post.return_value = ConnectionFailureContext()
        session.close = AsyncMock(side_effect=OSError("close failed"))

        with patch.object(chat_service_module.aiohttp, "ClientSession", return_value=session):
            with self.assertRaises(LINEOAError) as raised:
                await service.async_send_message("Ubot", "Uchat", {"type": "text"})

        self.assertIsInstance(
            raised.exception.__cause__,
            chat_service_module.aiohttp.ClientConnectionError,
        )
        session.close.assert_awaited_once_with()

    async def test_python_310_async_timeouts_are_wrapped(self):
        service = ChatService()

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "upload.bin"
            file_path.write_bytes(b"payload")
            operations = (
                lambda session: service.async_send_file(
                    "Ubot", "Uchat", str(file_path), session=session
                ),
                lambda session: service.async_send_message(
                    "Ubot", "Uchat", {"type": "text"}, session=session
                ),
                lambda session: service.async_get_chat_members(
                    "Ubot", "Uchat", session=session
                ),
                lambda session: service.async_get_chat_messages(
                    "Ubot", "Uchat", session=session
                ),
            )

            for operation in operations:
                with self.subTest(operation=operation):
                    session = Mock()
                    session.get.return_value = RaisingAsyncContext()
                    session.post.return_value = RaisingAsyncContext()
                    with patch.object(
                        chat_service_module.asyncio,
                        "TimeoutError",
                        LegacyAsyncioTimeoutError,
                    ):
                        with self.assertRaises(LINEOAError) as raised:
                            await operation(session)

                    self.assertIsInstance(
                        raised.exception.__cause__,
                        LegacyAsyncioTimeoutError,
                    )

    async def test_async_get_chat_members_rejects_missing_ids(self):
        service = ChatService()
        session = FakeAioSession()

        with self.assertRaisesRegex(LINEOAError, "required"):
            await service.async_get_chat_members("Ubot", "", session=session)

        self.assertEqual([], session.calls)

    async def test_async_history_and_members_reject_invalid_queries(self):
        service = ChatService()
        session = FakeAioSession()
        operations = (
            lambda: service.async_get_chat_messages(
                "",
                "Uchat",
                session=session,
            ),
            lambda: service.async_get_chat_messages(
                "Ubot",
                "Uchat",
                limit=True,
                session=session,
            ),
            lambda: service.async_get_chat_messages(
                "Ubot",
                "Uchat",
                before="",
                session=session,
            ),
            lambda: service.async_get_chat_members(
                "Ubot",
                "Uchat",
                limit=101,
                session=session,
            ),
        )

        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaises(LINEOAError):
                    await operation()

        self.assertEqual([], session.calls)

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
        self.assertEqual(120, session.calls[0][1]["timeout"].total)
        self.assertEqual(30, session.calls[1][1]["timeout"].total)

    async def test_async_message_history_matches_v3_sync_endpoint(self):
        service = ChatService(request_timeout=17)
        session = FakeAioSession()

        result = await service.async_get_chat_messages(
            "Ubot",
            "Uchat",
            before=123,
            session=session,
        )

        self.assertEqual({"list": []}, result)
        url, kwargs = session.calls[0]
        self.assertIn("/api/v3/", url)
        self.assertEqual(123, kwargs["params"]["before"])
        self.assertEqual(17, kwargs["timeout"].total)


if __name__ == "__main__":
    unittest.main()
