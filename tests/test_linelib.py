import importlib
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch


linelib_module = importlib.import_module("LINELib.LINELib")
LINELib = linelib_module.LINELib
config_module = importlib.import_module("LINELib.config")
ListenConfig = config_module.ListenConfig
RateLimitConfig = config_module.RateLimitConfig


def make_library(storage_path):
    storage_path.write_text('{"cookies": []}', encoding="utf-8")
    library = LINELib.__new__(LINELib)
    library.storage = str(storage_path)
    library._rate_limit = 18
    library._rate_limit_window = 60
    library._rate_limit_enabled = True
    library._session = object()
    library._xsrf_token = "xsrf"
    library._chat_service = Mock()
    library._bots = None
    return library


class LINELibTests(unittest.TestCase):
    def test_info_objects_reject_invalid_api_lists_as_library_errors(self):
        invalid_cases = (
            (linelib_module.BotsInfo, None, "Bot account list"),
            (linelib_module.BotsInfo, [None], "index 0"),
            (linelib_module.ChatsInfo, None, "Chat list"),
            (
                linelib_module.ChatsInfo,
                [{"chatType": "GROUP"}],
                "chatId",
            ),
        )

        for info_class, items, message in invalid_cases:
            with self.subTest(info_class=info_class, items=items):
                with self.assertRaisesRegex(linelib_module.LINEOAError, message):
                    info_class(items)

    def test_chat_info_repr_handles_null_profile(self):
        chats = linelib_module.ChatsInfo(
            [{"chatType": "USER", "chatId": "Uchat", "profile": None}]
        )

        self.assertIn("Uchat : Uchat", repr(chats))
        self.assertIn("Uchat : Uchat", repr(chats.user))

    def test_listen_config_normalizes_numeric_values(self):
        config = ListenConfig(
            ping_secs="30",
            reconnect_interval="2.5",
            max_reconnects="3",
            max_stream_seconds="120",
        )

        self.assertEqual(30, config.ping_secs)
        self.assertEqual(2.5, config.reconnect_interval)
        self.assertEqual(3, config.max_reconnects)
        self.assertEqual(120.0, config.max_stream_seconds)

    def test_configs_reject_non_finite_values(self):
        invalid_configs = (
            lambda: RateLimitConfig(window=float("nan")),
            lambda: RateLimitConfig(window=float("inf")),
            lambda: ListenConfig(reconnect_interval=float("nan")),
            lambda: ListenConfig(max_stream_seconds=float("inf")),
        )

        for create_config in invalid_configs:
            with self.subTest(create_config=create_config):
                with self.assertRaises(ValueError):
                    create_config()

    def test_rate_limit_config_normalizes_numbers_and_rejects_non_boolean(self):
        config = RateLimitConfig(limit="3", window="2.5", enabled=True)

        self.assertEqual(3, config.limit)
        self.assertEqual(2.5, config.window)
        with self.assertRaisesRegex(ValueError, "boolean"):
            RateLimitConfig(enabled="false")

    def test_partial_email_credentials_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "storage.json"

            with self.assertRaisesRegex(ValueError, "provided together"):
                LINELib(storage=str(storage_path), email="owner@example.com")

    def test_missing_cookie_storage_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "storage.json"

            with self.assertRaisesRegex(Exception, "cookie storage"):
                LINELib(storage=str(storage_path))

    def test_cookie_storage_without_usable_line_cookies_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "storage.json"
            storage_path.write_text(
                json.dumps(
                    {
                        "cookies": [
                            {
                                "name": "third-party",
                                "value": "blocked",
                                "domain": ".example.com",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(Exception, "usable LINE Business cookies"):
                LINELib(storage=str(storage_path))

    def test_cookie_restore_uses_selected_edge_headers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "storage.json"
            storage_path.write_text(
                '{"cookies": [{"name": "session", "value": "value", "domain": "chat.line.biz"}]}',
                encoding="utf-8",
            )
            library = LINELib(storage=str(storage_path), browser_channel="msedge")

        self.assertIn("Edg/151.0.0.0", library._session.headers["User-Agent"])
        self.assertIn("Microsoft Edge", library._session.headers["sec-ch-ua"])
        self.assertEqual(
            library._session.headers["User-Agent"],
            library._chat_service.browser_headers["User-Agent"],
        )

    def test_rate_limit_cleanup_uses_configured_window(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            library._rate_limit_window = 10
            Path(library.storage).write_text(
                '{"cookies": [], "SendTimestamps": [50.0, 95.0]}',
                encoding="utf-8",
            )
            with patch.object(linelib_module.time, "time", return_value=100.0):
                timestamps = library.get_send_timestamps()

        self.assertEqual([95.0], timestamps)

    def test_rate_limit_cleanup_discards_future_timestamps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            Path(library.storage).write_text(
                '{"cookies": [], "SendTimestamps": [95.0, 10000.0]}',
                encoding="utf-8",
            )
            with patch.object(linelib_module.time, "time", return_value=100.0):
                timestamps = library.get_send_timestamps()

        self.assertEqual([95.0], timestamps)

    def test_rate_limit_history_supports_limits_above_twenty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            library._rate_limit = 25
            for timestamp in range(25):
                library.add_send_timestamp(float(timestamp))

            stored = json.loads(Path(library.storage).read_text(encoding="utf-8"))

        self.assertEqual(25, len(stored["SendTimestamps"]))

    def test_concurrent_rate_limit_reservations_do_not_exceed_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            library._rate_limit = 10
            library._rate_limit_window = 60
            results = []

            def reserve():
                results.append(library._reserve_send_slot())

            threads = [threading.Thread(target=reserve) for _ in range(40)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            stored = json.loads(Path(library.storage).read_text(encoding="utf-8"))

        self.assertEqual(10, sum(result is None for result in results))
        self.assertEqual(10, len(stored["SendTimestamps"]))
        self.assertIn("cookies", stored)

    def test_disabled_rate_limit_does_not_record_send_slot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            library._rate_limit_enabled = False

            result = library._reserve_send_slot()
            stored = json.loads(Path(library.storage).read_text(encoding="utf-8"))

        self.assertIsNone(result)
        self.assertNotIn("SendTimestamps", stored)

    def test_async_cookie_header_respects_domain_and_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            library._session = linelib_module.requests.Session()
            library._session.cookies.set("api-cookie", "allowed", domain="chat.line.biz", path="/api")
            library._session.cookies.set("other-cookie", "blocked", domain="manager.line.biz", path="/")

            header = library._async_cookie_header()

        self.assertIn("api-cookie=allowed", header)
        self.assertNotIn("other-cookie", header)

    def test_flex_rate_limit_preserves_integer_return_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            library._rate_limit = 1
            Path(library.storage).write_text(
                json.dumps({"cookies": [], "SendTimestamps": [time.time()]}),
                encoding="utf-8",
            )

            with self.assertRaises(linelib_module.LINEOAError) as raised:
                library.create_and_send_flex(
                    bot_id="Ubot",
                    at_id="@bot",
                    chat_id="Uchat",
                    title="title",
                    image_url="https://example.com/image.png",
                )

        self.assertEqual("rate_limited", raised.exception.code)
        library._chat_service.create_and_send_flex.assert_not_called()

    def test_streaming_state_receives_session_and_xsrf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            library._chat_service.get_streaming_api_token.return_value = {
                "streamingApiToken": "stream-token",
                "connectionId": "connection",
            }
            library._chat_service.stream_events.return_value = []

            library.get_streaming_api_token_and_listen_stream_events("Ubot")

        library._chat_service.streaming_state.assert_called_once_with(
            bot_id="Ubot",
            state={"connectionId": "connection", "idle": True},
            session=library._session,
            xsrf_token="xsrf",
        )

    def test_empty_stream_event_id_resets_last_event_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            library._chat_service.get_streaming_api_token.return_value = {
                "streamingApiToken": "stream-token",
            }
            library._chat_service.stream_events.return_value = [
                {"id": "", "type": "chat", "payload": {}}
            ]

            last_event_id = library.get_streaming_api_token_and_listen_stream_events(
                "Ubot",
                last_event_id="old-id",
            )

        self.assertIsNone(last_event_id)

    def test_provider_failure_is_not_cached_as_an_empty_result(self):
        library = LINELib.__new__(LINELib)
        library._provider = None
        library._session = Mock()
        library._xsrf_token = "xsrf"
        library._chat_service = Mock(request_timeout=30)
        library._chat_service._session_headers.return_value = {}
        failed_response = Mock(ok=False, status_code=503)
        successful_response = Mock(ok=True)
        successful_response.json.return_value = {"providerId": "provider"}
        library._chat_service._request.side_effect = [failed_response, successful_response]

        with self.assertRaises(linelib_module.LINEOAError):
            _ = library.provider

        self.assertIsNone(library._provider)
        self.assertEqual({"providerId": "provider"}, library.provider)
        self.assertEqual(2, library._chat_service._request.call_count)

    def test_save_link_metadata_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            library.normalize_message_event = Mock(
                return_value={
                    "message_type": "link",
                    "message_id": "message",
                    "bot_id": "Ubot",
                    "chat_id": "Uchat",
                    "title": "Example",
                    "url": "https://example.com",
                    "text": "Example",
                    "timestamp": 1,
                    "raw": {},
                }
            )
            target = Path(temp_dir) / "nested" / "link"

            saved = library.save_message_media({}, str(target))

            saved_path = Path(saved)
            self.assertTrue(saved_path.exists())
            self.assertEqual("https://example.com", json.loads(saved_path.read_text(encoding="utf-8"))["url"])

    def test_failed_link_metadata_save_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            library.normalize_message_event = Mock(
                return_value={
                    "message_type": "link",
                    "message_id": "message",
                    "bot_id": "Ubot",
                    "chat_id": "Uchat",
                    "title": "Example",
                    "url": "https://example.com",
                    "text": "Example",
                    "timestamp": 1,
                    "raw": object(),
                }
            )
            target = Path(temp_dir) / "link.json"
            original = '{"preserve": true}\n'
            target.write_text(original, encoding="utf-8")

            with self.assertRaises(TypeError):
                library.save_message_media({}, str(target))

            self.assertEqual(original, target.read_text(encoding="utf-8"))


class AsyncLINELibTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_send_respects_rate_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            library._rate_limit = 2
            Path(library.storage).write_text(
                json.dumps({"cookies": [], "SendTimestamps": [time.time(), time.time()]}),
                encoding="utf-8",
            )
            library._chat_service.async_send_message = AsyncMock()

            result = await library.async_send_message("Uchat", "text", bot_id="Ubot")

        self.assertTrue(result["ratelimit"])
        library._chat_service.async_send_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
