from typing import Optional, List, Dict, Any, Callable
import urllib.parse
import requests
import os
import json
import time
from .exceptions import LINEOAError
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

class AuthService:
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
	def __init__(self, channel_id: Optional[str] = None, channel_secret: Optional[str] = None, access_token: Optional[str] = None, cookie_store_path: Optional[str] = None):
		self.channel_id = channel_id
		self.channel_secret = channel_secret
		self.access_token = access_token
		self.cookie_store_path = cookie_store_path

	def login_with_email_and_2fa(self, email: Optional[str], password: Optional[str], get_2fa_code_callback: Optional[Callable], recaptcha_response: str = "", stay_logged_in: bool = True, xsrf_token: Optional[str] = None, cookies: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
		# Cookie storage
		if self.cookie_store_path and os.path.exists(self.cookie_store_path):
			if os.path.getsize(self.cookie_store_path) == 0:
				raise LINEOAError("Cookie storage load error: cookie file is empty. Please save logged-in cookies.")
			try:
				with open(self.cookie_store_path, "r", encoding="utf-8") as f:
					data = json.load(f)
				if data.get("email") == email and "cookies" in data:
					session = requests.Session()
					for c in data["cookies"]:
						session.cookies.set(c["name"], c["value"], domain=c.get("domain"))
					chat_cookies = {c["name"] for c in data["cookies"] if c.get("domain") == "chat.line.biz"}
					for c in data["cookies"]:
						if c["name"] not in chat_cookies and c.get("domain") in [".line.biz", ".manager.line.biz", "manager.line.biz", "account.line.biz"]:
							session.cookies.set(c["name"], c["value"], domain="chat.line.biz")
					user_info = {"user_name": data.get("user_name")}
					return {"session": session, "user_info": user_info}
			except Exception as e:
				raise LINEOAError(f"Cookie storage load error: {e}")
		if email is None and password is None:
			session = requests.Session()
			user_info = {"user_name": None}
			login_url = "https://account.line.biz/login?redirectUri=https%3A%2F%2Faccount.line.biz%2Foauth2%2Fcallback%3Fclient_id%3D10%26code_challenge%3D4x53SnbmZOYxDeiDFpINCIeh9t1HYiSmIY2E7CblxVY%26code_challenge_method%3DS256%26redirect_uri%3Dhttps%253A%252F%252Fmanager.line.biz%252Fapi%252Foauth2%252FbizId%252Fcallback%26response_type%3Dcode%26state%3DUxTSXVJiwgOWD4cnrk68RCXBwhPLPkBI"
			chrome_options = Options()
			chrome_options.add_experimental_option("detach", True)
			driver = webdriver.Chrome(options=chrome_options)
			driver.get(login_url)
			while True:
				time.sleep(2)
				try:
					current_url = driver.current_url
					if current_url.startswith("https://manager.line.biz/"):
						break
				except Exception as e:
					raise LINEOAError(f"Error while checking current URL: {e}")
			driver.get("https://chat.line.biz/")
			time.sleep(2)
			driver.get("https://chat.line.biz/api/v1/bots?limit=1000&noFilter=true")
			time.sleep(2)
			bots_json = None
			try:
				pre = driver.find_element("tag name", "pre")
				bots_json = json.loads(pre.text)
			except Exception:
				try:
					bots_json = json.loads(driver.find_element("tag name", "body").text)
				except Exception as e:
					raise LINEOAError(f"Failed to parse bots JSON: {e}")
			bot_ids = [b["botId"] for b in bots_json.get("list", []) if b.get("botId", "").startswith("U")]
			all_cookies = driver.get_cookies()[:]
			for bot_id in bot_ids:
				url = f"https://chat.line.biz/{bot_id}"
				driver.get(url)
				time.sleep(2)
				all_cookies.extend(driver.get_cookies())
			driver.quit()
			seen = set()
			combined_cookies_to_save = []
			for cookie in all_cookies:
				try:
					key = (cookie['name'], cookie.get('domain'))
					if key not in seen:
						combined_cookies_to_save.append({
							"name": cookie['name'],
							"value": cookie['value'],
							"domain": cookie.get('domain')
						})
						seen.add(key)
				except Exception as e:
					raise LINEOAError(f"Error while processing cookies: {e}")
			for c in combined_cookies_to_save:
				try:
					session.cookies.set(c["name"], c["value"], domain=c.get("domain"))
				except Exception as e:
					raise LINEOAError(f"Error while setting session cookies: {e}")
			if self.cookie_store_path:
				try:
					with open(self.cookie_store_path, "w", encoding="utf-8") as f:
						json.dump({
							"user_name": user_info.get("user_name"),
							"cookies": combined_cookies_to_save
						}, f, ensure_ascii=False, indent=2)
				except Exception as e:
					raise LINEOAError(f"Cookie storage save error: {e}")
			return {"session": session, "user_info": user_info, "bot_ids": bot_ids}
		raise LINEOAError("login_with_email_and_2fa failed: no valid login path")

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
		xsrf_resp = session.get("https://chat.line.biz/api/v1/csrfToken")
		xsrf_token = xsrf_resp.json().get("token")
		login_resp = self.login_with_email(
			email, password, recaptcha_response="", stay_logged_in=True, xsrf_token=xsrf_token, cookies=session.cookies.get_dict()
		)
		if login_resp.get("status") == "needReCaptchaVerification":
			raise LINEOAError("reCAPTCHA verification is required. Manual intervention or external service integration is needed.")
		params = {
			"client_id": client_id,
			"code_challenge": code_challenge,
			"code_challenge_method": "S256",
			"redirect_uri": redirect_uri,
			"response_type": "code",
			"state": state,
			"status": "success"
		}
		auth_url = "https://account.line.biz/oauth2/callback?" + urllib.parse.urlencode(params)
		resp = session.get(auth_url, allow_redirects=False)
		if resp.status_code == 302 and "location" in resp.headers:
			loc = resp.headers["location"]
			parsed = urllib.parse.urlparse(loc)
			query = urllib.parse.parse_qs(parsed.query)
			code = query.get("code", [None])[0]
			return code
		raise LINEOAError("Failed to obtain authorization code")

	def get_access_token(self) -> str:
		"""
		Extend to implement access token acquisition API, etc.
		:return: Access token string
		:raises LINEOAError: When not set
		 """
		if self.access_token:
			return self.access_token
		raise LINEOAError("Access Token is not set")

	def login_with_email(self, email: str, password: str, recaptcha_response: str = "", stay_logged_in: bool = True, xsrf_token: Optional[str] = None, cookies: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
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
		url = "https://account.line.biz/api/login/email"
		headers = {
			"Content-Type": "application/json",
			"Accept": "application/json, text/plain, */*"
		}
		if xsrf_token:
			headers["x-xsrf-token"] = xsrf_token
		payload = {
			"email": email,
			"password": password,
			"gRecaptchaResponse": recaptcha_response,
			"stayLoggedIn": stay_logged_in
		}
		try:
			response = requests.post(url, headers=headers, json=payload, cookies=cookies)
			response.raise_for_status()
			return response.json()
		except Exception as e:
			raise LINEOAError(f"login_with_email failed: {e}")
