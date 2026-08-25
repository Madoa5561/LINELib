from typing import Dict

from .exceptions import LINEOAError


WINDOWS_CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)
WINDOWS_EDGE_USER_AGENT = f"{WINDOWS_CHROME_USER_AGENT} Edg/151.0.0.0"
WINDOWS_CHROME_SEC_CH_UA = (
    '"Not=A?Brand";v="99", "Google Chrome";v="151", "Chromium";v="151"'
)
WINDOWS_EDGE_SEC_CH_UA = (
    '"Not=A?Brand";v="99", "Microsoft Edge";v="151", "Chromium";v="151"'
)


def browser_headers_for_channel(browser_channel: str = "chrome") -> Dict[str, str]:
    """Return a consistent Windows 11 browser identity for LINE requests."""
    if not isinstance(browser_channel, str):
        raise LINEOAError(
            "browser_channel must be a Google Chrome or Microsoft Edge channel."
        )
    channel = browser_channel.lower()
    if channel.startswith("msedge"):
        user_agent = WINDOWS_EDGE_USER_AGENT
        sec_ch_ua = WINDOWS_EDGE_SEC_CH_UA
    elif channel.startswith("chrome"):
        user_agent = WINDOWS_CHROME_USER_AGENT
        sec_ch_ua = WINDOWS_CHROME_SEC_CH_UA
    else:
        raise LINEOAError(
            "browser_channel must be a Google Chrome or Microsoft Edge channel."
        )
    return {
        "User-Agent": user_agent,
        "sec-ch-ua": sec_ch_ua,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
