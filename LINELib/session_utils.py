from typing import Any, Dict, Iterable, Optional


CHAT_COOKIE_DOMAINS = ("chat.line.biz", ".chat.line.biz", "manager.line.biz", ".line.biz")
CHAT_TOKEN_COOKIE_NAMES = ("__Host-chat-ses", "chat-device-group", "XSRF-TOKEN")


def iter_cookies(session: Any) -> Iterable[Any]:
    cookies = getattr(session, "cookies", None)
    if cookies is None:
        return []
    return cookies


def cookie_domain(cookie: Any) -> str:
    return getattr(cookie, "domain", "") or ""


def get_xsrf_token(session: Any) -> Optional[str]:
    for cookie in iter_cookies(session):
        if getattr(cookie, "name", None) == "XSRF-TOKEN" and "chat.line.biz" in cookie_domain(cookie):
            return getattr(cookie, "value", None)
    return None


def get_cookie_dict(session: Any, domains=CHAT_COOKIE_DOMAINS) -> Dict[str, str]:
    cookies = getattr(session, "cookies", None)
    if cookies is None:
        return {}

    result = {}
    get_dict = getattr(cookies, "get_dict", None)
    if callable(get_dict):
        for domain in domains:
            try:
                result.update(get_dict(domain=domain))
            except Exception:
                pass
        return result

    for cookie in iter_cookies(session):
        domain = cookie_domain(cookie)
        if any(target.strip(".") in domain for target in domains):
            name = getattr(cookie, "name", None)
            value = getattr(cookie, "value", None)
            if name is not None and value is not None:
                result[name] = value
    return result


def get_stream_cookie_dict(session: Any) -> Dict[str, str]:
    result = get_cookie_dict(session, domains=("chat.line.biz", ".chat.line.biz"))
    for cookie in iter_cookies(session):
        name = getattr(cookie, "name", None)
        if name in CHAT_TOKEN_COOKIE_NAMES:
            result[name] = str(getattr(cookie, "value", ""))
    return result


def cookie_header(cookies: Dict[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in cookies.items())
