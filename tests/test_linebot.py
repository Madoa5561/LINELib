import functools
import threading
import unittest
from unittest.mock import Mock, PropertyMock, patch

from LINELib.exceptions import LINEOAError
from LINELib.linebot import LineBot


def make_bot(normalized):
    bot = LineBot.__new__(LineBot)
    bot.handlers = {}
    bot._lib = Mock()
    bot._lib.normalize_message_event.return_value = normalized
    bot._listen_lock = threading.Lock()
    return bot


class StubbornThread:
    def is_alive(self):
        return True

    def join(self, timeout=None):
        return None


class LineBotTests(unittest.TestCase):
    def test_listen_start_failure_restores_stopped_state(self):
        class FailingListenThread:
            def __init__(self, *args, **kwargs):
                pass

            def start(self):
                raise RuntimeError("thread resources unavailable")

        bot = make_bot({"kind": "unknown"})
        bot._listen_thread = None
        bot._stop_event = threading.Event()
        bot.running = False
        bot._resolve_bot_id = Mock(return_value="Ubot")

        with (
            patch("LINELib.linebot.threading.Thread", FailingListenThread),
            self.assertRaisesRegex(RuntimeError, "resources unavailable"),
        ):
            bot.listen(block=False)

        self.assertFalse(bot.running)
        self.assertTrue(bot._stop_event.is_set())
        self.assertIsNone(bot._listen_thread)

    def test_concurrent_listen_calls_start_only_one_polling_thread(self):
        real_thread = threading.Thread
        resolve_barrier = threading.Barrier(2)

        class FakeListenThread:
            created = []

            def __init__(self, *args, **kwargs):
                self.started = False
                self.__class__.created.append(self)

            def is_alive(self):
                return self.started

            def start(self):
                self.started = True

            def join(self, timeout=None):
                return None

        bot = make_bot({"kind": "unknown"})
        bot._listen_thread = None
        bot._stop_event = threading.Event()
        bot.running = False
        bot._polling_loop = Mock()

        def resolve_bot_id(botid=None):
            resolve_barrier.wait(timeout=2)
            return "Ubot"

        bot._resolve_bot_id = resolve_bot_id
        results = []

        def listen():
            try:
                results.append(bot.listen(block=False))
            except Exception as error:
                results.append(error)

        with patch("LINELib.linebot.threading.Thread", FakeListenThread):
            callers = [real_thread(target=listen) for _ in range(2)]
            for caller in callers:
                caller.start()
            for caller in callers:
                caller.join(timeout=3)

        self.assertTrue(all(not caller.is_alive() for caller in callers))
        self.assertEqual(1, len(FakeListenThread.created))
        self.assertEqual(1, sum(isinstance(result, RuntimeError) for result in results))

    def test_interactive_login_options_are_forwarded(self):
        otp_callback = Mock(return_value="123456")
        with patch("LINELib.linebot.LINELib") as library_class:
            library_class.return_value.bots.ids = {}

            LineBot(
                email="owner@example.com",
                password="test-password",
                get_2fa_code_callback=otp_callback,
                interactive_login=True,
                browser_channel="msedge",
                interactive_timeout=120,
            )

        _, kwargs = library_class.call_args
        self.assertIs(otp_callback, kwargs["get_2fa_code_callback"])
        self.assertTrue(kwargs["interactive_login"])
        self.assertEqual("msedge", kwargs["browser_channel"])
        self.assertEqual(120, kwargs["interactive_timeout"])

    def test_default_interactive_browser_is_chrome(self):
        with patch("LINELib.linebot.LINELib") as library_class:
            library_class.return_value.bots.ids = {}
            LineBot()

        _, kwargs = library_class.call_args
        self.assertEqual("chrome", kwargs["browser_channel"])

    def test_constructor_reuses_validated_bot_ids_without_refetching(self):
        library = Mock()
        library._bot_ids = ["Ubot"]
        type(library).bots = PropertyMock(
            side_effect=AssertionError("bot accounts were fetched twice")
        )

        with patch("LINELib.linebot.LINELib", return_value=library):
            bot = LineBot()

        self.assertEqual(["Ubot"], bot._bot_ids)
        library.close.assert_not_called()

    def test_constructor_failure_closes_library_without_masking_error(self):
        library = Mock()
        type(library)._bot_ids = PropertyMock(
            side_effect=LINEOAError("bot id initialization failed")
        )
        library.close.side_effect = OSError("close failed")

        with patch("LINELib.linebot.LINELib", return_value=library):
            with self.assertRaisesRegex(LINEOAError, "bot id initialization failed"):
                LineBot()

        library.close.assert_called_once_with()

    def test_media_event_routes_to_on_media_with_normalized_data(self):
        normalized = {"kind": "media", "message_type": "image", "message_id": "1"}
        bot = make_bot(normalized)
        received = []
        bot.handlers["on_media"] = received.append
        event = {
            "type": "chat",
            "payload": {
                "subEvent": "message",
                "payload": {"type": "message", "message": {"type": "image"}},
            },
        }

        bot.dispatch("chat", event)

        self.assertEqual(normalized, received[0]["normalized"])

    def test_media_event_falls_back_to_on_message(self):
        bot = make_bot({"kind": "sticker", "message_type": "sticker"})
        received = []
        bot.handlers["on_message"] = received.append

        bot.dispatch("chat", {"payload": {"subEvent": "message", "payload": {"type": "message"}}})

        self.assertEqual(1, len(received))

    def test_handler_error_is_isolated_for_callable_without_name(self):
        bot = make_bot({"kind": "text", "message_type": "text"})

        def raise_handler_error(message, event):
            raise RuntimeError(message)

        bot.handlers["on_text"] = functools.partial(
            raise_handler_error,
            "expected handler error",
        )

        with patch("LINELib.linebot.lineoa_logger.exception") as log_exception:
            bot.dispatch("chat", {"payload": {}})

        log_exception.assert_called_once()
        self.assertIn("partial", log_exception.call_args.args[0])
        self.assertIn("expected handler error", log_exception.call_args.args[0])

    def test_documented_media_methods_delegate_to_library(self):
        bot = make_bot({"kind": "unknown"})
        bot._lib.save_message_media.return_value = "saved.jpg"

        result = bot.save_message_media({"id": "1"}, "output")

        self.assertEqual("saved.jpg", result)
        bot._lib.save_message_media.assert_called_once_with({"id": "1"}, "output")

    def test_get_chats_resolves_default_bot_id(self):
        bot = make_bot({"kind": "unknown"})
        bot._bot_ids = ["Udefault"]
        bot._lib.getChats.return_value = {"list": []}

        result = bot.getChats()

        self.assertEqual({"list": []}, result)
        bot._lib.getChats.assert_called_once_with(bot_id="Udefault", limit=25)

    def test_default_bot_does_not_fall_back_to_unfiltered_accounts(self):
        bot = make_bot({"kind": "unknown"})
        bot._bot_ids = []

        with self.assertRaisesRegex(RuntimeError, "chat-enabled"):
            bot._resolve_bot_id()

        bot._lib.get_bots.assert_not_called()

    def test_send_message_rejects_missing_required_values(self):
        bot = make_bot({"kind": "unknown"})

        with self.assertRaisesRegex(ValueError, "chat_id"):
            bot.sendMessage(text="hello")
        with self.assertRaisesRegex(ValueError, "chat_id"):
            bot.sendMessage(chat_id="", text="hello")
        with self.assertRaisesRegex(ValueError, "text"):
            bot.sendMessage(chat_id="Uchat")
        with self.assertRaisesRegex(ValueError, "text"):
            bot.sendMessage(chat_id="Uchat", text="")
        with self.assertRaisesRegex(ValueError, "file_path"):
            bot.sendFile(chat_id="Uchat", file_path="")

    def test_stop_from_listener_thread_does_not_join_itself(self):
        bot = make_bot({"kind": "unknown"})
        bot.running = True
        bot._stop_event = threading.Event()
        bot._listen_thread = threading.current_thread()

        bot.stop()

        self.assertFalse(bot.running)
        self.assertTrue(bot._stop_event.is_set())
        bot._lib._close_stream.assert_called_once_with()

    def test_stop_keeps_running_true_when_thread_did_not_exit(self):
        bot = make_bot({"kind": "unknown"})
        bot.running = True
        bot._stop_event = threading.Event()
        bot._listen_thread = StubbornThread()

        bot.stop()

        self.assertTrue(bot.running)
        bot._lib._close_stream.assert_called_once_with()

    def test_close_stops_polling_and_closes_library(self):
        bot = make_bot({"kind": "unknown"})
        bot.stop = Mock()

        bot.close()

        bot.stop.assert_called_once_with()
        bot._lib.close.assert_called_once_with()

    def test_last_event_id_is_scoped_per_bot(self):
        bot = make_bot({"kind": "unknown"})
        bot._stop_event = threading.Event()
        bot._last_event_ids = {}
        bot.device_type = ""
        bot.client_type = "PC"
        bot.ping_secs = 60
        bot.reconnect_interval = 0
        bot.max_reconnects = None
        bot.listen_config = Mock(max_stream_seconds=60)
        calls = []

        def listen(**kwargs):
            calls.append((kwargs["bot_id"], kwargs["last_event_id"]))
            bot._stop_event.set()
            return f"{kwargs['bot_id']}-last"

        bot._lib.get_streaming_api_token_and_listen_stream_events.side_effect = listen

        bot._polling_loop("UbotA")
        bot._stop_event.clear()
        bot._polling_loop("UbotB")

        self.assertEqual([("UbotA", None), ("UbotB", None)], calls)
        self.assertEqual("UbotA-last", bot._last_event_ids["UbotA"])
        self.assertEqual("UbotB-last", bot._last_event_ids["UbotB"])

    def test_last_event_id_survives_connection_failure(self):
        bot = make_bot({"kind": "unknown"})
        bot._stop_event = threading.Event()
        bot._last_event_ids = {"Ubot": "old-id"}
        bot.device_type = ""
        bot.client_type = "PC"
        bot.ping_secs = 60
        bot.reconnect_interval = 0
        bot.max_reconnects = 0
        bot.listen_config = Mock(max_stream_seconds=60)

        def fail_after_event(**kwargs):
            kwargs["on_event"]({"id": "new-id", "type": "chat", "payload": {}})
            raise RuntimeError("connection lost")

        bot._lib.get_streaming_api_token_and_listen_stream_events.side_effect = fail_after_event

        bot._polling_loop("Ubot")

        self.assertEqual("new-id", bot._last_event_ids["Ubot"])

    def test_empty_event_id_clears_reconnect_state(self):
        bot = make_bot({"kind": "unknown"})
        bot._stop_event = threading.Event()
        bot._last_event_ids = {"Ubot": "old-id"}
        bot.device_type = ""
        bot.client_type = "PC"
        bot.ping_secs = 60
        bot.reconnect_interval = 0
        bot.max_reconnects = None
        bot.listen_config = Mock(max_stream_seconds=60)

        def reset_event_id(**kwargs):
            kwargs["on_event"]({"id": "", "type": "chat", "payload": {}})
            bot._stop_event.set()
            return None

        bot._lib.get_streaming_api_token_and_listen_stream_events.side_effect = reset_event_id

        bot._polling_loop("Ubot")

        self.assertNotIn("Ubot", bot._last_event_ids)


if __name__ == "__main__":
    unittest.main()
