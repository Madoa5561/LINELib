import json
from dataclasses import dataclass
from typing import Any, Dict, Generator, Iterable, Optional


@dataclass(frozen=True)
class SSEEvent:
    id: Optional[str]
    event: Optional[str]
    data: str

    @property
    def payload(self) -> Any:
        try:
            return json.loads(self.data)
        except Exception:
            return self.data

    def as_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "event": self.event, "data": self.data}

    def message_payload(self) -> Optional[Dict[str, Any]]:
        payload = self.payload
        if not isinstance(payload, dict):
            return None
        inner = payload.get("payload")
        if isinstance(inner, dict):
            message = inner.get("message")
            if isinstance(message, dict):
                return message
        message = payload.get("message")
        if isinstance(message, dict):
            return message
        return None

    def image_url(self) -> Optional[str]:
        normalized = self.normalized_message()
        if not normalized:
            return None
        return normalized.get("media_url")

    def normalized_message(self) -> Optional[Dict[str, Any]]:
        payload = self.payload
        if not isinstance(payload, dict):
            return None
        inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
        message = None
        if isinstance(inner, dict):
            message = inner.get("message")
        if not isinstance(message, dict):
            return None
        message_type = message.get("type")
        content_provider = message.get("contentProvider") if isinstance(message.get("contentProvider"), dict) else {}
        content_hash = message.get("contentHash") or content_provider.get("contentHash")
        bot_id = payload.get("botId")
        media_url = None
        if bot_id and content_hash and message_type in {"image", "video", "file"}:
            media_url = f"https://chat-content.line.biz/bot/{bot_id}/{content_hash}/preview"

        sticker_id = message.get("stickerId") or (message.get("contentProvider") or {}).get("stickerId")
        package_id = message.get("packageId") or (message.get("contentProvider") or {}).get("packageId")
        audio = message.get("audio") if isinstance(message.get("audio"), dict) else {}
        file_name = message.get("fileName") or message.get("name") or content_provider.get("fileName") or content_provider.get("file_name")
        extension = None
        if isinstance(file_name, str) and "." in file_name:
            extension = file_name.rsplit(".", 1)[-1].lower()
        elif message_type == "image":
            extension = "jpg"
        elif message_type == "video":
            extension = "mp4"
        elif message_type == "file":
            extension = "bin"
        elif message_type == "audio":
            extension = "m4a"
        elif message_type == "sticker":
            extension = "png"

        return {
            "kind": "media" if message_type in {"image", "video", "file"} else message_type,
            "message_type": message_type,
            "bot_id": bot_id,
            "chat_id": payload.get("chatId"),
            "message_id": message.get("id"),
            "timestamp": message.get("timestamp") or inner.get("timestamp"),
            "content_hash": content_hash,
            "media_url": media_url,
            "sticker_media_url": f"https://stickershop.line-scdn.net/stickershop/v1/sticker/{sticker_id}/android/sticker.png" if sticker_id else None,
            "expired": message.get("expired"),
            "expired_at": message.get("expiredAt"),
            "text": message.get("text"),
            "url": message.get("url") or message.get("linkUrl") or (message.get("contentProvider") or {}).get("url"),
            "title": message.get("title") or message.get("linkTitle"),
            "sticker_id": sticker_id,
            "package_id": package_id,
            "file_name": file_name,
            "extension": extension,
            "duration": message.get("duration") or audio.get("duration"),
            "audio": audio,
            "raw": message,
        }


class SSEParser:
    @staticmethod
    def iter_events(lines: Iterable[str]) -> Generator[SSEEvent, None, None]:
        event_id = None
        event_type = None
        data_lines = []

        def build_event():
            if not data_lines:
                return None
            return SSEEvent(
                id=event_id,
                event=event_type,
                data="\n".join(data_lines),
            )

        for line in lines:
            if line is None:
                continue
            line = line.rstrip("\r\n")
            if line.startswith(":") or line == "":
                event = build_event()
                if event is not None:
                    yield event
                event_id = None
                event_type = None
                data_lines = []
                continue
            if line.startswith("id:"):
                event_id = line[3:].lstrip()
            elif line.startswith("event:"):
                event_type = line[6:].lstrip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())

        event = build_event()
        if event is not None:
            yield event
