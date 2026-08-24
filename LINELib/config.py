from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class RateLimitConfig:
    limit: int = 18
    window: float = 60
    enabled: bool = True

    def __post_init__(self):
        limit = int(self.limit)
        window = float(self.window)
        if limit < 1:
            raise ValueError("rate_limit must be greater than 0")
        if window <= 0:
            raise ValueError("rate_limit_window must be greater than 0")
        if not isinstance(self.enabled, bool):
            raise ValueError("rate_limit_enabled must be a boolean")
        object.__setattr__(self, "limit", limit)
        object.__setattr__(self, "window", window)


@dataclass(frozen=True)
class ListenConfig:
    ping_secs: int = 60
    device_type: str = ""
    client_type: str = "PC"
    reconnect_interval: float = 5
    max_reconnects: Optional[int] = None
    max_stream_seconds: float = 82800

    def __post_init__(self):
        ping_secs = int(self.ping_secs)
        reconnect_interval = float(self.reconnect_interval)
        max_reconnects = None if self.max_reconnects is None else int(self.max_reconnects)
        max_stream_seconds = float(self.max_stream_seconds)
        if ping_secs < 1:
            raise ValueError("ping_secs must be greater than 0")
        if reconnect_interval < 0:
            raise ValueError("reconnect_interval must be greater than or equal to 0")
        if max_reconnects is not None and max_reconnects < 0:
            raise ValueError("max_reconnects must be greater than or equal to 0")
        if max_stream_seconds <= 0:
            raise ValueError("max_stream_seconds must be greater than 0")
        object.__setattr__(self, "ping_secs", ping_secs)
        object.__setattr__(self, "reconnect_interval", reconnect_interval)
        object.__setattr__(self, "max_reconnects", max_reconnects)
        object.__setattr__(self, "max_stream_seconds", max_stream_seconds)
