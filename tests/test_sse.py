import json
import unittest

from LINELib.sse import SSEEvent, SSEParser


class SSETests(unittest.TestCase):
    def test_keepalive_comment_does_not_split_event(self):
        events = list(SSEParser.iter_events(["id: 1", "data: first", ": keepalive", "data: second", ""]))

        self.assertEqual(1, len(events))
        self.assertEqual("first\nsecond", events[0].data)

    def test_sticker_message_is_normalized(self):
        payload = {
            "botId": "Ubot",
            "chatId": "Uchat",
            "payload": {
                "type": "message",
                "message": {"id": "1", "type": "sticker", "stickerId": "123"},
            },
        }

        normalized = SSEEvent(id="1", event="chat", data=json.dumps(payload)).normalized_message()

        self.assertEqual("sticker", normalized["kind"])
        self.assertEqual("123", normalized["sticker_id"])
        self.assertTrue(normalized["sticker_media_url"].endswith("/123/android/sticker.png"))

    def test_invalid_content_provider_shape_does_not_raise(self):
        payload = {
            "botId": "Ubot",
            "payload": {
                "type": "message",
                "message": {"id": "1", "type": "text", "contentProvider": "invalid"},
            },
        }

        normalized = SSEEvent(id="1", event="chat", data=json.dumps(payload)).normalized_message()

        self.assertEqual("text", normalized["message_type"])


if __name__ == "__main__":
    unittest.main()
