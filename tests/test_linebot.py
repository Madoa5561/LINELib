import threading
import unittest
from unittest.mock import Mock, patch

from LINELib.linebot import LineBot


def make_bot(normalized):
    bot = LineBot.__new__(LineBot)
    bot.handlers = {}
    bot._lib = Mock()
    bot._lib.normalize_message_event.return_value = normalized
    return bot


class LineBotTests(unittest.TestCase):
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
        bot._lib.getChats.assert_called_once_with(bot_id="Udefault", limit=100)

    def test_send_message_rejects_missing_required_values(self):
        bot = make_bot({"kind": "unknown"})

        with self.assertRaisesRegex(ValueError, "chat_id"):
            bot.sendMessage(text="hello")
        with self.assertRaisesRegex(ValueError, "text"):
            bot.sendMessage(chat_id="Uchat")

    def test_stop_from_listener_thread_does_not_join_itself(self):
        bot = make_bot({"kind": "unknown"})
        bot.running = True
        bot._stop_event = threading.Event()
        bot._listen_thread = threading.current_thread()

        bot.stop()

        self.assertFalse(bot.running)
        self.assertTrue(bot._stop_event.is_set())


if __name__ == "__main__":
    unittest.main()
