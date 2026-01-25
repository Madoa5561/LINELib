from enum import Enum

class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"
    CALL_GUIDE = "callGuide"
    STICKER = "sticker"
    FILE = "file"
    VIDEO = "video"
    AUDIO = "audio"
    LOCATION = "location"
    EMOJI = "emoji"

MESSAGE_PAYLOAD_EXAMPLES = {
    MessageType.TEXT: {
        "type": "text",
        "text": "こんにちは"
    },
    MessageType.CALL_GUIDE: {
        "type": "callGuide"
    },
    MessageType.STICKER: {
        "type": "sticker",
        "packageId": "6325",
        "stickerId": "10979904"
    },
    MessageType.EMOJI: {
        "type": "emoji",
        "productId": "670e0cce840a8236ddd4ee4c",
        "emojiId": "003"
    },
}
