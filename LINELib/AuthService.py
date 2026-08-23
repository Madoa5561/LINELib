import json
import os
import urllib.parse
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from .exceptions import InteractiveLoginRequired, LINEOAError


class _LoginConfigParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.global_config: Dict[str, Any] = {}
        self.page_config: Dict[str, Any] = {}

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag != "script":
            return
        attributes = dict(attrs)
        if attributes.get("id") != "__config__":
            return
        try:
            self.global_config = json.loads(attributes.get("data-global") or "{}")
            self.page_config = json.loads(attributes.get("data-page") or "{}")
        except (TypeError, json.JSONDecodeError) as error:
            raise LINEOAError(f"Failed to parse login page configuration: {error}") from error

class AuthService:
	MANAGER_URL = "https://manager.line.biz/"
	CHAT_URL = "https://chat.line.biz/"
	CHAT_CSRF_URL = "https://chat.line.biz/api/v1/csrfToken"
	CHAT_BOTS_URL = "https://chat.line.biz/api/v1/bots?limit=1000&noFilter=true"
	EMAIL_LOGIN_URL = "https://account.line.biz/api/login/email"
	ALLOWED_LOGIN_HOSTS = {"account.line.biz", "manager.line.biz", "chat.line.biz"}

	def __init__(self, channel_id: Optional[str] = None, channel_secret: Optional[str] = None, access_token: Optional[str] = None, cookie_store_path: Optional[str] = None, request_timeout: float = 30):
		self.channel_id = channel_id
		self.channel_secret = channel_secret
		self.access_token = access_token
		self.cookie_store_path = cookie_store_path
		self.request_timeout = request_timeout

	def get_uid_map_from_at_ids(self, at_id_list: List[str], chat_service: Any) -> Dict[str, str]:
		"""
		Get a map from @ID list to U-ID (internal ID)
		:param at_id_list: ['@xxxx', ...]
		:param chat_service: ChatService instance
		:return: dict {@id: u_id}
		 """
		uid_map = {}
		try:
			bot_accounts = chat_service.get_bot_accounts()
			for bot in bot_accounts.get('list', []):
				at_id = bot.get('basicSearchId')
				u_id = bot.get('botId')
				if at_id and u_id and at_id in at_id_list:
					uid_map[at_id] = u_id
		except Exception as e:
			LINEOAError(f"Failed to get UID map from @IDs: {e}")
		return uid_map

	def _load_cookie_storage(self) -> Optional[Dict[str, Any]]:
		if not self.cookie_store_path or not os.path.exists(self.cookie_store_path):
			return None
		if os.path.getsize(self.cookie_store_path) == 0:
			raise LINEOAError("Cookie storage load error: cookie file is empty.")
		try:
			with open(self.cookie_store_path, "r", encoding="utf-8") as file:
				data = json.load(file)
		except (OSError, json.JSONDecodeError) as error:
			raise LINEOAError(f"Cookie storage load error: {error}") from error
		if not isinstance(data, dict) or not isinstance(data.get("cookies"), list):
			raise LINEOAError("Cookie storage load error: cookies must be a list.")
		return data

	def _session_from_storage(self, data: Dict[str, Any]) -> requests.Session:
		session = requests.Session()
		for cookie in data["cookies"]:
			if not isinstance(cookie, dict):
				continue
			name = cookie.get("name")
			value = cookie.get("value")
			if not isinstance(name, str) or not isinstance(value, str):
				continue
			kwargs: Dict[str, Any] = {"path": cookie.get("path") or "/"}
			if cookie.get("domain"):
				kwargs["domain"] = cookie["domain"]
			expires = cookie.get("expiry", cookie.get("expires"))
			if isinstance(expires, (int, float)):
				kwargs["expires"] = int(expires)
			if isinstance(cookie.get("secure"), bool):
				kwargs["secure"] = cookie["secure"]
			session.cookies.set(name, value, **kwargs)
		return session

	def _save_cookie_storage(self, session: requests.Session, user_name: Optional[str]) -> None:
		if not self.cookie_store_path:
			return
		cookies = []
		for cookie in session.cookies:
			item: Dict[str, Any] = {
				"name": cookie.name,
				"value": cookie.value,
				"domain": cookie.domain,
				"path": cookie.path,
			}
			if cookie.expires is not None:
				item["expiry"] = cookie.expires
			if cookie.secure:
				item["secure"] = True
			cookies.append(item)
		try:
			with open(self.cookie_store_path, "w", encoding="utf-8") as file:
				json.dump({"user_name": user_name, "cookies": cookies}, file, ensure_ascii=False, indent=2)
		except OSError as error:
			raise LINEOAError(f"Cookie storage save error: {error}") from error

	def _get_login_config(self, html: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
		parser = _LoginConfigParser()
		parser.feed(html)
		if not parser.global_config:
			raise LINEOAError("Login page configuration was not found.")
		return parser.global_config, parser.page_config

	def _start_login(self, session: requests.Session) -> Tuple[str, str, Dict[str, Any]]:
		try:
			response = session.get(self.MANAGER_URL, allow_redirects=True, timeout=self.request_timeout)
			response.raise_for_status()
		except requests.RequestException as error:
			raise LINEOAError(f"Failed to open the LINE Business login page: {error}") from error
		parsed_url = urllib.parse.urlparse(response.url)
		if parsed_url.scheme != "https" or parsed_url.hostname != "account.line.biz" or parsed_url.path != "/login":
			raise LINEOAError("LINE Business did not return the expected login page.")
		global_config, page_config = self._get_login_config(response.text)
		xsrf_token = global_config.get("csrfToken")
		if not isinstance(xsrf_token, str) or not xsrf_token:
			raise LINEOAError("The login page did not provide a CSRF token.")
		return response.url, xsrf_token, page_config

	def _validate_redirect_uri(self, redirect_uri: Any) -> str:
		if not isinstance(redirect_uri, str) or not redirect_uri:
			raise LINEOAError("The login response did not provide a redirect URI.")
		parsed = urllib.parse.urlparse(redirect_uri)
		if parsed.scheme != "https" or parsed.hostname not in self.ALLOWED_LOGIN_HOSTS:
			raise LINEOAError("The login response contained an unsafe redirect URI.")
		return redirect_uri

	def _initialize_chat_session(self, session: requests.Session) -> Tuple[Optional[str], List[str]]:
		try:
			home_response = session.get(self.CHAT_URL, allow_redirects=True, timeout=self.request_timeout)
			home_response.raise_for_status()
			if urllib.parse.urlparse(home_response.url).hostname != "chat.line.biz":
				raise InteractiveLoginRequired("additional_verification")

			csrf_response = session.get(self.CHAT_CSRF_URL, timeout=self.request_timeout)
			csrf_response.raise_for_status()
			csrf_payload = csrf_response.json()
			if not isinstance(csrf_payload, dict):
				raise LINEOAError("The chat CSRF endpoint returned an invalid response.")
			xsrf_token = csrf_payload.get("token")
			if isinstance(xsrf_token, str) and xsrf_token:
				session.cookies.set("XSRF-TOKEN", xsrf_token, domain="chat.line.biz", path="/")

			bots_response = session.get(self.CHAT_BOTS_URL, timeout=self.request_timeout)
			bots_response.raise_for_status()
			bots_payload = bots_response.json()
		except InteractiveLoginRequired:
			raise
		except (requests.RequestException, ValueError) as error:
			raise LINEOAError(f"Failed to initialize the chat session: {error}") from error
		if not isinstance(bots_payload, dict) or not isinstance(bots_payload.get("list"), list):
			raise LINEOAError("The chat bots endpoint returned an invalid response.")

		bot_ids = [
			bot["botId"]
			for bot in bots_payload.get("list", [])
			if isinstance(bot, dict) and isinstance(bot.get("botId"), str) and bot["botId"].startswith("U")
		]
		user_name = bots_payload.get("userName")
		return user_name if isinstance(user_name, str) else None, bot_ids

	def login_with_email_and_2fa(self, email: Optional[str], password: Optional[str], get_2fa_code_callback: Optional[Callable], recaptcha_response: str = "", stay_logged_in: bool = True, xsrf_token: Optional[str] = None, cookies: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
		"""Log in without Selenium, reusing stored cookies when they remain valid."""
		stored_data = self._load_cookie_storage()
		if stored_data is not None:
			stored_session = self._session_from_storage(stored_data)
			try:
				user_name, bot_ids = self._initialize_chat_session(stored_session)
				return {
					"session": stored_session,
					"user_info": {"user_name": user_name or stored_data.get("user_name")},
					"bot_ids": bot_ids,
				}
			except (LINEOAError, InteractiveLoginRequired):
				if not email or not password:
					raise

		if not email or not password:
			raise LINEOAError("Email and password are required when no valid cookie session is available.")

		session = requests.Session()
		login_url, page_xsrf_token, _ = self._start_login(session)
		login_response = self.login_with_email(
			email=email,
			password=password,
			recaptcha_response=recaptcha_response,
			stay_logged_in=stay_logged_in,
			xsrf_token=page_xsrf_token,
			session=session,
			referer=login_url,
		)
		status = login_response.get("status")
		if status == "needReCaptchaVerification":
			raise InteractiveLoginRequired("recaptcha")
		if status != "success":
			raise LINEOAError(f"Email login failed with status: {status or 'unknown'}")
		if login_response.get("twoFactorSetupModalTargetUri"):
			raise InteractiveLoginRequired("two_factor_setup")

		redirect_uri = self._validate_redirect_uri(login_response.get("redirectUri"))
		try:
			redirect_response = session.get(redirect_uri, allow_redirects=True, timeout=self.request_timeout)
			redirect_response.raise_for_status()
		except requests.RequestException as error:
			raise LINEOAError(f"Failed to complete the login redirect: {error}") from error
		redirect_host = urllib.parse.urlparse(redirect_response.url).hostname
		if redirect_host == "account.line.biz":
			raise InteractiveLoginRequired("additional_verification")
		if redirect_host not in {"manager.line.biz", "chat.line.biz"}:
			raise LINEOAError("The login redirect did not finish on a LINE Business service.")

		user_name, bot_ids = self._initialize_chat_session(session)
		self._save_cookie_storage(session, user_name)
		return {"session": session, "user_info": {"user_name": user_name}, "bot_ids": bot_ids}

	def login_and_get_token(self, email: str, password: str, client_id: str, code_challenge: str, redirect_uri: str, state: str, session: Optional[requests.Session] = None) -> Optional[str]:
		"""
		Automate OAuth2 authentication flow with email and password only to obtain authorization code (code) template
		:param email: Email address
		:param password: Password
		:param client_id: OAuth2 client ID
		:param code_challenge: PKCE challenge
		:param redirect_uri: Redirect URI
		:param state: state parameter
		:param session: requests.Session (newly created if omitted)
		:return: code (authorization code) or None
		 """
		session = session or requests.Session()
		params = {
			"client_id": client_id,
			"code_challenge": code_challenge,
			"code_challenge_method": "S256",
			"redirect_uri": redirect_uri,
			"response_type": "code",
			"state": state,
		}
		authorize_url = "https://account.line.biz/oauth2/authorize?" + urllib.parse.urlencode(params)
		try:
			login_page = session.get(authorize_url, allow_redirects=True, timeout=self.request_timeout)
			login_page.raise_for_status()
		except requests.RequestException as error:
			raise LINEOAError(f"Failed to start OAuth authentication: {error}") from error
		global_config, _ = self._get_login_config(login_page.text)
		login_resp = self.login_with_email(
			email,
			password,
			recaptcha_response="",
			stay_logged_in=True,
			xsrf_token=global_config.get("csrfToken"),
			session=session,
			referer=login_page.url,
		)
		if login_resp.get("status") == "needReCaptchaVerification":
			raise InteractiveLoginRequired("recaptcha")
		if login_resp.get("status") != "success":
			raise LINEOAError("Email login did not complete the OAuth authentication.")

		next_url = self._validate_redirect_uri(login_resp.get("redirectUri"))
		for _ in range(10):
			parsed = urllib.parse.urlparse(next_url)
			query = urllib.parse.parse_qs(parsed.query)
			if "state" in query and query["state"][0] != state:
				raise LINEOAError("OAuth state validation failed.")
			code = query.get("code", [None])[0]
			if code:
				expected_redirect = urllib.parse.urlparse(redirect_uri)
				if (
					query.get("state", [None])[0] != state
					or parsed.scheme != expected_redirect.scheme
					or parsed.netloc != expected_redirect.netloc
					or parsed.path != expected_redirect.path
				):
					raise LINEOAError("OAuth redirect validation failed.")
				return code
			self._validate_redirect_uri(next_url)
			try:
				response = session.get(next_url, allow_redirects=False, timeout=self.request_timeout)
			except requests.RequestException as error:
				raise LINEOAError(f"Failed to follow the OAuth redirect: {error}") from error
			if not response.is_redirect or "location" not in response.headers:
				break
			next_url = urllib.parse.urljoin(next_url, response.headers["location"])
		raise LINEOAError("Failed to obtain authorization code.")

	def get_access_token(self) -> str:
		if self.access_token:
			return self.access_token
		raise LINEOAError("Access Token is not set")

	def login_with_email(self, email: str, password: str, recaptcha_response: str = "", stay_logged_in: bool = True, xsrf_token: Optional[str] = None, cookies: Optional[Dict[str, str]] = None, session: Optional[requests.Session] = None, referer: Optional[str] = None) -> Dict[str, Any]:
		"""
		Log in to LINE Business Account with email and password
		POST https://account.line.biz/api/login/email
		:param email: Email address
		:param password: Password
		:param recaptcha_response: reCAPTCHA response (if needed)
		:param stay_logged_in: Stay logged in
		:param xsrf_token: XSRF token (if needed)
		:param cookies: Session cookies (if needed)
		:return: dict (API response)
		 """
		session = session or requests.Session()
		if cookies:
			session.cookies.update(cookies)
		headers = {
			"Content-Type": "application/json",
			"Accept": "application/json, text/plain, */*",
			"Origin": "https://account.line.biz",
		}
		if xsrf_token:
			headers["X-XSRF-TOKEN"] = xsrf_token
		if referer:
			headers["Referer"] = referer
		payload = {
			"email": email,
			"password": password,
			"gRecaptchaResponse": recaptcha_response,
			"stayLoggedIn": stay_logged_in
		}
		try:
			response = session.post(self.EMAIL_LOGIN_URL, headers=headers, json=payload, timeout=self.request_timeout)
			response_payload = response.json()
			if not isinstance(response_payload, dict):
				raise ValueError("login response must be a JSON object")
			if response.ok or (400 <= response.status_code < 500 and isinstance(response_payload.get("status"), str)):
				return response_payload
			response.raise_for_status()
			return response_payload
		except (requests.RequestException, ValueError) as error:
			raise LINEOAError(f"login_with_email failed: {error}") from error

