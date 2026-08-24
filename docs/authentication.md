# 認証

LINELibは、LINE Official Account ManagerへログインしたCookieとXSRF tokenを使って `chat.line.biz` の内部APIへアクセスします。通常は `LineBot` または `LINELib` に認証設定を渡し、`AuthService` を直接操作する必要はありません。

## 認証の選択順

メールアドレスとパスワードを渡した場合、認証は次の順番です。

1. `cookie_path` / `storage` に保存済みCookieがあれば、実際に `chat.line.biz` を開いて有効性を確認する
2. Cookieが有効なら、そのSessionを再利用してログインを終了する
3. Cookieが無効で `interactive_login=True` なら、最初から可視ブラウザで公式ログイン画面を開く
4. Cookieが無効で `interactive_login=False` なら、メールログインAPIへ直接HTTPリクエストを送る
5. 必要ならメールOTPを同じログインSessionで検証する
6. `chat.line.biz` のCSRF tokenとBot一覧を取得し、成功したCookieを保存する

メールアドレスとパスワードを渡さない場合、`LINELib` はCookieファイルをSessionへ復元します。Cookieファイルがない、空、形式不正、またはCookie一覧が空の場合は `LINEOAError` で初期化を中止します。`LineBot` は続けてBot一覧も取得するため、期限切れCookieなど実際の認証失敗も初期化中に通知されます。

## 保存Cookieを再利用する

```python
from LINELib import LineBot

bot = LineBot(cookie_path="lineoa-storage.json")
print(bot.getBots())
```

Cookieファイルには、LINE Businessの利用に必要な `.line.biz` 配下のCookie名・値・domain・path・有効期限などとユーザー名がJSONで保存されます。reCAPTCHAなど第三者ドメインのCookie、メールアドレス、パスワードは保存しません。同じファイルにはローカル送信レート制限の時刻履歴も保存されます。

Cookieはログイン権限を持つ秘密情報です。

- Gitへcommitしない
- チャット、Issue、ログへ貼らない
- 他人と共有しない
- バックアップ先のアクセス権を制限する
- 失効または漏えいが疑われる場合は公式管理画面側でセッションを無効化する

## 可視Chromeによる対話ログイン

reCAPTCHAが発生する可能性がある初回ログインでは、この方式を推奨します。

```powershell
python -m pip install "lineoa[interactive-login]"
```

```python
from getpass import getpass

from LINELib import LineBot


def get_otp() -> str:
    return input("メールに届いた6桁のログインコード: ").strip()


bot = LineBot(
    cookie_path="lineoa-storage.json",
    email=input("メールアドレス: ").strip(),
    password=getpass("パスワード: "),
    get_2fa_code_callback=get_otp,
    interactive_login=True,
    browser_channel="chrome",
    interactive_timeout=300,
)
```

処理の流れ:

1. インストール済みGoogle Chromeを可視状態で起動する
2. 公式ログイン画面にメールアドレスとパスワードを入力する
3. ログインボタンを押し、公式ページ内のreCAPTCHAを動作させる
4. 視覚的なreCAPTCHAが表示された場合だけ、利用者がブラウザ上で操作する
5. メール認証画面へ進んだ場合はブラウザCookieをHTTP Sessionへ移す
6. callbackから受け取った6桁OTPを検証する
7. 管理画面への遷移とBot一覧取得を確認し、Cookieを保存する

LINELibはreCAPTCHAを解読・回避しません。隠しreCAPTCHAは公式ページが通常どおり実行します。ブラウザは常にheadlessではなく可視状態です。

## Edgeを使う

Edgeを使う場合は1引数だけ変更します。

```python
bot = LineBot(
    cookie_path="lineoa-storage.json",
    email="your-email@example.com",
    password="your-password",
    get_2fa_code_callback=lambda: input("OTP: ").strip(),
    interactive_login=True,
    browser_channel="msedge",
)
```

対応channelはChrome系とEdge系だけです。それ以外は、ブラウザと一致しないUser-Agentを誤送信しないため `LINEOAError` になります。

## Windows 11固定のブラウザヘッダー

ログイン関連リクエストは、Windows 11上の可視ブラウザで確認した値へ固定されています。Windows 11のUser-Agentでも互換性のためOS部分は `Windows NT 10.0` です。

- Chrome User-Agent: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36`
- Edge User-Agent: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0`
- Chrome `sec-ch-ua`: `"Not=A?Brand";v="99", "Google Chrome";v="151", "Chromium";v="151"`
- Edge `sec-ch-ua`: `"Not=A?Brand";v="99", "Microsoft Edge";v="151", "Chromium";v="151"`
- `sec-ch-ua-mobile`: `?0`
- `sec-ch-ua-platform`: `"Windows"`

これはログイン画面、Cookie復元Session、OTP検証、ログイン後リダイレクトで使用する認証用ヘッダーの説明です。個々のチャットAPIが送信するヘッダーまで同一であることを意味しません。

## ブラウザを使わない直接HTTPログイン

`interactive_login=False` が既定値です。保存Cookieが利用できずメールアドレスとパスワードがある場合、公式ページからCSRF tokenとログイン設定を取得し、メールログインAPIへ直接送信します。

```python
from LINELib import InteractiveLoginRequired, LineBot

try:
    bot = LineBot(
        cookie_path="lineoa-storage.json",
        email="your-email@example.com",
        password="your-password",
        get_2fa_code_callback=lambda: input("OTP: ").strip(),
        interactive_login=False,
    )
except InteractiveLoginRequired as error:
    print(error.reason)
```

reCAPTCHAが不要ならブラウザなしで完了します。必要な場合は `InteractiveLoginRequired` が発生し、`reason == "recaptcha"` になります。その場合は `interactive_login=True` でやり直してください。

## メールOTP

`get_2fa_code_callback` は、引数を受け取らず6桁の文字列を返す関数です。

```python
def get_otp() -> str:
    code = input("メールOTP: ").strip()
    return code
```

- OTPが必要な場合だけ呼ばれます
- 不要なログインでは呼ばれません
- 6桁の数字以外は `LINEOAError` になります
- callbackを省略した状態でOTPが必要になると `InteractiveLoginRequired(reason="email_otp")` になります
- コードはCookieファイルへ保存されません
- 古いコード、別セッションのコード、期限切れコードは成功しません

## 例外

```python
from LINELib import InteractiveLoginRequired, LINEOAError

try:
    pass
except InteractiveLoginRequired as error:
    print("追加操作:", error.reason)
except LINEOAError as error:
    print("code:", error.code)
    print("details:", error.details)
```

`InteractiveLoginRequired` は `LINEOAError` のサブクラスです。先に捕捉してください。実装で使用される主な `reason`:

| reason | 意味 | 次の操作 |
|---|---|---|
| `recaptcha` | 直接HTTPログインでreCAPTCHAが必要 | `interactive_login=True` で可視ブラウザを使う |
| `email_otp` | OTPが必要だがcallbackがない | callbackを渡して再実行する |
| `two_factor_setup` | 追加の2要素設定が必要 | 公式画面で設定を完了する |
| `additional_verification` | 通常フロー外の追加確認が必要 | 公式管理画面へ手動ログインし、状態を確認する |

`LINEOAError` はHTTPエラー、不正レスポンス、CSRF不足、危険なredirect、Cookie形式不正、ブラウザ起動失敗などを表します。`message` に概要、場合によって `code` と `details` に追加情報があります。

## `AuthService` を直接使う場合

通常は不要ですが、独自の認証管理では次の戻り値を受け取れます。

```python
from LINELib import AuthService

auth = AuthService(cookie_store_path="lineoa-storage.json")
result = auth.login_with_email_and_2fa(
    email="your-email@example.com",
    password="your-password",
    get_2fa_code_callback=lambda: input("OTP: ").strip(),
    interactive_login=True,
)
session = result["session"]
user_info = result["user_info"]
bot_ids = result["bot_ids"]
```

低レベルメソッドの全一覧は[低レベルAPI](low-level-api.md#authservice)を参照してください。
