import importlib
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch


linelib_module = importlib.import_module("LINELib.LINELib")
LINELib = linelib_module.LINELib


def make_library(storage_path):
    library = LINELib.__new__(LINELib)
    library.storage = str(storage_path)
    library._storage_cache = {"cookies": []}
    library._rate_limit = 18
    library._rate_limit_window = 60
    library._rate_limit_enabled = True
    library._session = object()
    library._xsrf_token = "xsrf"
    library._chat_service = Mock()
    library._bots = None
    return library


class LINELibTests(unittest.TestCase):
    def test_rate_limit_cleanup_uses_configured_window(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            library._rate_limit_window = 10
            library._storage_cache["SendTimestamps"] = [50.0, 95.0]
            with patch.object(linelib_module.time, "time", return_value=100.0):
                timestamps = library.get_send_timestamps()

        self.assertEqual([95.0], timestamps)

    def test_rate_limit_history_supports_limits_above_twenty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            library._rate_limit = 25
            for timestamp in range(25):
                library.add_send_timestamp(float(timestamp))

        self.assertEqual(25, len(library._storage_cache["SendTimestamps"]))

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


class AsyncLINELibTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_send_respects_rate_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            library = make_library(Path(temp_dir) / "storage.json")
            library._rate_limit = 2
            library.get_send_timestamps = Mock(return_value=[time.time(), time.time()])
            library._chat_service.async_send_message = AsyncMock()

            result = await library.async_send_message("Uchat", "text", bot_id="Ubot")

        self.assertTrue(result["ratelimit"])
        library._chat_service.async_send_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
