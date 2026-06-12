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
