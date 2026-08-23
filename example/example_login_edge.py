import os
from getpass import getpass

from LINELib import LineBot


def request_email_otp() -> str:
    return input("メールに届いた6桁のログインコード: ").strip()


def main() -> None:
    email = os.environ.get("LINEOA_EMAIL") or input("LINE Business IDのメールアドレス: ").strip()
    password = os.environ.get("LINEOA_PASSWORD") or getpass("LINE Business IDのパスワード: ")
    bot = LineBot(
        cookie_path=os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json"),
        email=email,
        password=password,
        get_2fa_code_callback=request_email_otp,
        interactive_login=True,
        browser_channel="msedge",
    )
    print(bot.getBots())


if __name__ == "__main__":
    main()
