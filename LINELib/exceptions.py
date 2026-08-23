from typing import Optional, Any

class LINEOAError(Exception):
    def __init__(self, message: Optional[str], code: Optional[Any] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.code = code
        self.details = details


class InteractiveLoginRequired(LINEOAError):
    """Raised when LINE requires a browser-only verification step."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(
            "Interactive login is required to complete reCAPTCHA or additional verification.",
            code="interactive_login_required",
        )
