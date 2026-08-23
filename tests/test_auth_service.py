import html
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from LINELib.AuthService import AuthService
from LINELib.exceptions import InteractiveLoginRequired


class StubResponse:
    def __init__(self, *, url, payload=None, text="", status_code=200, headers=None):
        self.url = url
        self._payload = payload
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}
        self.is_redirect = status_code in {301, 302, 303, 307, 308}

    @property
    def ok(self):
        return self.status_code < 400

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


def login_page():
    global_config = html.escape(json.dumps({"csrfToken": "account-xsrf"}), quote=True)
    page_config = html.escape(json.dumps({"sitekey": "recaptcha-site-key"}), quote=True)
    return (
        '<script id="__config__" '
        f'data-global="{global_config}" data-page="{page_config}"></script>'
    )


def mock_session():
    session = Mock()
    session.cookies = requests.cookies.RequestsCookieJar()
    return session


class AuthServiceTests(unittest.TestCase):
    def test_email_login_uses_official_http_flow_and_saves_cookies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "lineoa-storage.json"
            service = AuthService(cookie_store_path=str(storage_path))
            session = mock_session()
            session.get.side_effect = [
                StubResponse(url="https://account.line.biz/login?redirectUri=masked", text=login_page()),
                StubResponse(url="https://manager.line.biz/"),
                StubResponse(url="https://chat.line.biz/"),
                StubResponse(url=service.CHAT_CSRF_URL, payload={"token": "chat-xsrf"}),
                StubResponse(
                    url=service.CHAT_BOTS_URL,
                    payload={"userName": "owner", "list": [{"botId": "Ubot"}]},
                ),
            ]
            session.post.return_value = StubResponse(
                url=service.EMAIL_LOGIN_URL,
                payload={
                    "status": "success",
                    "redirectUri": "https://account.line.biz/oauth2/callback?state=masked",
                },
            )

            with patch("LINELib.AuthService.requests.Session", return_value=session):
                result = service.login_with_email_and_2fa(
                    "owner@example.com",
                    "test-password",
                    get_2fa_code_callback=None,
                )

            self.assertEqual(["Ubot"], result["bot_ids"])
            _, post_kwargs = session.post.call_args
            self.assertEqual("account-xsrf", post_kwargs["headers"]["X-XSRF-TOKEN"])
            self.assertEqual("owner@example.com", post_kwargs["json"]["email"])
            self.assertEqual("test-password", post_kwargs["json"]["password"])
            saved = json.loads(storage_path.read_text(encoding="utf-8"))
            self.assertNotIn("email", saved)
            self.assertTrue(any(cookie["name"] == "XSRF-TOKEN" for cookie in saved["cookies"]))

    def test_recaptcha_requirement_stops_before_redirect(self):
        service = AuthService()
        session = mock_session()
        session.get.return_value = StubResponse(
            url="https://account.line.biz/login?redirectUri=masked",
            text=login_page(),
        )
        session.post.return_value = StubResponse(
            url=service.EMAIL_LOGIN_URL,
            payload={"status": "needReCaptchaVerification"},
            status_code=400,
        )

        with patch("LINELib.AuthService.requests.Session", return_value=session):
            with self.assertRaises(InteractiveLoginRequired) as raised:
                service.login_with_email_and_2fa(
                    "owner@example.com",
                    "test-password",
                    get_2fa_code_callback=None,
                )

        self.assertEqual("recaptcha", raised.exception.reason)
        self.assertEqual(1, session.get.call_count)

    def test_stored_cookies_are_reused_without_storing_email(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "lineoa-storage.json"
            storage_path.write_text(
                json.dumps(
                    {
                        "user_name": "owner",
                        "cookies": [
                            {
                                "name": "session",
                                "value": "cookie-value",
                                "domain": "chat.line.biz",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            service = AuthService(cookie_store_path=str(storage_path))

            with patch.object(service, "_initialize_chat_session", return_value=(None, ["Ubot"])):
                result = service.login_with_email_and_2fa(
                    email=None,
                    password=None,
                    get_2fa_code_callback=None,
                )

        self.assertEqual(["Ubot"], result["bot_ids"])
        self.assertEqual("owner", result["user_info"]["user_name"])

    def test_external_redirect_is_rejected(self):
        service = AuthService()
        with self.assertRaisesRegex(Exception, "unsafe redirect"):
            service._validate_redirect_uri("https://example.com/callback")


if __name__ == "__main__":
    unittest.main()
