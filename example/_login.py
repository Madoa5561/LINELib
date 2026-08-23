import os
from typing import Any

from LINELib import LINELib, LineBot


def _credentials(require_credentials: bool) -> tuple[str | None, str | None]:
    email = os.environ.get("LINEOA_EMAIL")
    password = os.environ.get("LINEOA_PASSWORD")
    if bool(email) != bool(password):
        raise RuntimeError("LINEOA_EMAIL and LINEOA_PASSWORD must be set together.")
    if require_credentials and not email:
        raise RuntimeError("LINEOA_EMAIL and LINEOA_PASSWORD are required for initial login.")
    return email, password


def _otp_code() -> str:
    return input("メールに届いた6桁のログインコード: ").strip()


def _auth_options(require_credentials: bool) -> dict[str, Any]:
    email, password = _credentials(require_credentials)
    if not email or not password:
        return {}
    return {
        "email": email,
        "password": password,
        "get_2fa_code_callback": _otp_code,
        "interactive_login": True,
        "browser_channel": os.environ.get("LINEOA_BROWSER_CHANNEL", "msedge"),
        "interactive_timeout": float(os.environ.get("LINEOA_INTERACTIVE_TIMEOUT", "300")),
    }


def create_bot(*, require_credentials: bool = False, **options: Any) -> LineBot:
    login_options = _auth_options(require_credentials)
    login_options.update(options)
    return LineBot(
        cookie_path=os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json"),
        **login_options,
    )


def create_library(*, require_credentials: bool = False, **options: Any) -> LINELib:
    login_options = _auth_options(require_credentials)
    login_options.update(options)
    return LINELib(
        storage=os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json"),
        **login_options,
    )
