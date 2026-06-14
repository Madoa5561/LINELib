from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class RateLimitConfig:
    limit: int = 18
    window: float = 60
    enabled: bool = True

    def __post_init__(self):
        if int(self.limit) < 1:
            raise ValueError("rate_limit must be greater than 0")
        if float(self.window) <= 0:
            raise ValueError("rate_limit_window must be greater than 0")


@dataclass(frozen=True)
class ListenConfig:
    ping_secs: int = 60
    device_type: str = ""
    client_type: str = "PC"
    reconnect_interval: float = 5
    max_reconnects: Optional[int] = None

    def __post_init__(self):
        if int(self.ping_secs) < 1:
            raise ValueError("ping_secs must be greater than 0")
        if float(self.reconnect_interval) < 0:
            raise ValueError("reconnect_interval must be greater than or equal to 0")
        if self.max_reconnects is not None and int(self.max_reconnects) < 0:
            raise ValueError("max_reconnects must be greater than or equal to 0")
