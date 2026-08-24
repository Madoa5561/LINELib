import html
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from LINELib.AuthService import AuthService
from LINELib.exceptions import InteractiveLoginRequired, LINEOAError


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
    def test_request_timeout_rejects_non_finite_values(self):
        for value in (float("nan"), float("inf"), 0, "invalid"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(LINEOAError, "request_timeout"):
                    AuthService(request_timeout=value)

    def test_interactive_timeout_is_validated_before_browser_start(self):
        service = AuthService()

        for value in (float("nan"), float("inf"), 0, "invalid"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(LINEOAError, "interactive_timeout"):
                    service._login_with_interactive_browser(
                        "owner@example.com",
                        "test-password",
                        None,
                        True,
                        "chrome",
                        value,
                    )

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
            session.headers.update.assert_called_once_with(
                service._browser_headers_for_channel("chrome")
            )
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

    def test_interactive_login_starts_chrome_before_direct_http_login(self):
        service = AuthService()
        expected = {"session": Mock(), "user_info": {}, "bot_ids": ["Ubot"]}

        with (
            patch.object(service, "_load_cookie_storage", return_value=None),
            patch.object(service, "_start_login") as start_login,
            patch.object(
                service,
                "_login_with_interactive_browser",
                return_value=expected,
            ) as interactive_login,
        ):
            result = service.login_with_email_and_2fa(
                "owner@example.com",
                "test-password",
                get_2fa_code_callback=None,
                interactive_login=True,
            )

        self.assertIs(expected, result)
        start_login.assert_not_called()
        self.assertEqual("chrome", interactive_login.call_args.kwargs["browser_channel"])

    def test_browser_headers_match_windows_chrome_and_edge(self):
        service = AuthService()
        chrome_headers = service._browser_headers_for_channel("chrome")
        edge_headers = service._browser_headers_for_channel("msedge")

        self.assertIn("Windows NT 10.0", chrome_headers["User-Agent"])
        self.assertIn("Chrome/151.0.0.0", chrome_headers["User-Agent"])
        self.assertNotIn("Edg/", chrome_headers["User-Agent"])
        self.assertIn("Google Chrome", chrome_headers["sec-ch-ua"])
        self.assertIn("Edg/151.0.0.0", edge_headers["User-Agent"])
        self.assertIn("Microsoft Edge", edge_headers["sec-ch-ua"])
        self.assertEqual('"Windows"', chrome_headers["sec-ch-ua-platform"])
        self.assertEqual('"Windows"', edge_headers["sec-ch-ua-platform"])

    def test_stored_session_uses_selected_browser_headers(self):
        service = AuthService()
        session = service._session_from_storage(
            {
                "cookies": [
                    {"name": "line-session", "value": "line", "domain": "chat.line.biz"},
                    {"name": "third-party", "value": "blocked", "domain": ".google.com"},
                ]
            },
            "msedge",
        )

        self.assertEqual(service.WINDOWS_EDGE_USER_AGENT, session.headers["User-Agent"])
        self.assertEqual(service.WINDOWS_EDGE_SEC_CH_UA, session.headers["sec-ch-ua"])
        self.assertEqual("line", session.cookies.get("line-session", domain="chat.line.biz"))
        self.assertNotIn("third-party", session.cookies)

    def test_unknown_browser_channel_is_rejected(self):
        service = AuthService()
        with self.assertRaisesRegex(Exception, "Google Chrome or Microsoft Edge"):
            service._browser_headers_for_channel("chromium")

    def test_email_otp_callback_completes_verification(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "lineoa-storage.json"
            service = AuthService(cookie_store_path=str(storage_path))
            session = mock_session()
            session.get.side_effect = [
                StubResponse(url="https://account.line.biz/login?redirectUri=masked", text=login_page()),
                StubResponse(url=service.EMAIL_VERIFICATION_URL),
                StubResponse(url="https://manager.line.biz/"),
                StubResponse(url="https://chat.line.biz/"),
                StubResponse(url=service.CHAT_CSRF_URL, payload={"token": "chat-xsrf"}),
                StubResponse(url=service.CHAT_BOTS_URL, payload={"list": [{"botId": "Ubot"}]}),
            ]
            session.post.side_effect = [
                StubResponse(
                    url=service.EMAIL_LOGIN_URL,
                    payload={"status": "success", "redirectUri": service.EMAIL_VERIFICATION_URL},
                ),
                StubResponse(
                    url=service.EMAIL_VERIFICATION_VERIFY_URL,
                    payload={
                        "status": "success",
                        "redirectUri": "https://account.line.biz/oauth2/callback?state=masked",
                    },
                ),
            ]
            otp_callback = Mock(return_value="123456")

            with patch("LINELib.AuthService.requests.Session", return_value=session):
                result = service.login_with_email_and_2fa(
                    "owner@example.com",
                    "test-password",
                    get_2fa_code_callback=otp_callback,
                )

            self.assertEqual(["Ubot"], result["bot_ids"])
            otp_callback.assert_called_once_with()
            otp_call = session.post.call_args_list[1]
            self.assertEqual(service.EMAIL_VERIFICATION_VERIFY_URL, otp_call.args[0])
            self.assertEqual({"code": "123456"}, otp_call.kwargs["json"])
            self.assertEqual("account-xsrf", otp_call.kwargs["headers"]["X-XSRF-TOKEN"])

    def test_email_otp_rejects_non_six_digit_code(self):
        service = AuthService()
        session = mock_session()

        with self.assertRaisesRegex(Exception, "exactly six digits"):
            service.verify_email_otp(session, "12345x", "account-xsrf")

        session.post.assert_not_called()

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

    def test_cookie_save_preserves_rate_limit_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "lineoa-storage.json"
            storage_path.write_text(
                json.dumps({"SendTimestamps": [1.0], "FinalsendTime": 1}),
                encoding="utf-8",
            )
            service = AuthService(cookie_store_path=str(storage_path))
            session = requests.Session()
            session.cookies.set("session", "value", domain="chat.line.biz")
            session.cookies.set("recaptcha", "third-party", domain=".google.com")

            service._save_cookie_storage(session, "owner")

            stored = json.loads(storage_path.read_text(encoding="utf-8"))

        self.assertEqual([1.0], stored["SendTimestamps"])
        self.assertEqual(1, stored["FinalsendTime"])
        self.assertEqual("owner", stored["user_name"])
        self.assertEqual(["session"], [cookie["name"] for cookie in stored["cookies"]])

    def test_explicit_cookies_and_xsrf_are_used_for_direct_login(self):
        service = AuthService()
        session = requests.Session()
        login_with_email = Mock(return_value={"status": "needReCaptchaVerification"})

        with (
            patch.object(service, "_load_cookie_storage", return_value=None),
            patch("LINELib.AuthService.requests.Session", return_value=session),
            patch.object(service, "_start_login", return_value=("https://account.line.biz/login", "page-xsrf", {})),
            patch.object(service, "login_with_email", login_with_email),
        ):
            with self.assertRaises(InteractiveLoginRequired):
                service.login_with_email_and_2fa(
                    "owner@example.com",
                    "test-password",
                    get_2fa_code_callback=None,
                    xsrf_token="explicit-xsrf",
                    cookies={"account-session": "cookie-value"},
                )

        self.assertEqual(
            "cookie-value",
            session.cookies.get("account-session", domain="account.line.biz", path="/"),
        )
        self.assertEqual("explicit-xsrf", login_with_email.call_args.kwargs["xsrf_token"])

    def test_external_redirect_is_rejected(self):
        service = AuthService()
        with self.assertRaisesRegex(Exception, "unsafe redirect"):
            service._validate_redirect_uri("https://example.com/callback")


if __name__ == "__main__":
    unittest.main()
