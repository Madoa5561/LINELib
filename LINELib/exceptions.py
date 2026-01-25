from typing import Optional, Any
from .logger import lineoa_logger

class LINEOAError(Exception):
    def __init__(self, message: Optional[str], code: Optional[Any] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.code = code
        self.details = details
        lineoa_logger.error(f"[LINEOAError] {message}")
        if code:
            lineoa_logger.error(f"[LINEOAError] code: {code}")
        if details:
            lineoa_logger.error(f"[LINEOAError] details: {details}")
