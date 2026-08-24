# はじめに

このページでは、LINELibをインストールし、ログイン状態を用意して、Bot一覧の確認、テキスト送信、イベント受信までを行います。

## 必要なもの

- Python 3.10以上
- 自分が管理権限を持つLINE Official Account
- LINEヤフーBusiness IDのメールアドレスとパスワード
- 初回ログイン時にメールOTPを受信できる環境
- 対話ログインを使う場合は、Windows 11へインストール済みのGoogle ChromeまたはMicrosoft Edge

## インストール

PyPI版:

```powershell
python -m pip install lineoa
```

可視ブラウザによる初回ログインも使う場合:

```powershell
python -m pip install "lineoa[interactive-login]"
```

リポジトリを編集しながら使う場合:

```powershell
git clone https://github.com/Madoa5561/LINELib.git
Set-Location LINELib
python -m pip install -e ".[interactive-login]"
```

対話ログインはPlaywrightの `channel="chrome"` または `channel="msedge"` で、OSにインストール済みのブラウザを起動します。Playwright同梱Chromiumのダウンロードは不要です。

## IDの確認

初回ログイン後、利用できるOfficial Accountを表示します。

```python
from LINELib import LineBot

bot = LineBot(cookie_path="lineoa-storage.json")
accounts = bot.getBots()
print(accounts)
print(accounts.ids)
```

`accounts.ids` は `{basicSearchIdまたは名前: bot_id}` の辞書で、Botモードを含む取得済みアカウントを確認できます。`bot_id` を省略できる一部メソッドでは、`responseMode=BOT` を除いた最初のチャット対応Botが選ばれます。複数のチャット対応アカウントを管理している場合は、意図しないアカウントを避けるため明示してください。

チャット一覧から送信先IDを確認できます。

```python
bot_id = next(iter(accounts.ids.values()))
chats = bot.getChats(bot_id=bot_id, limit=25)
for chat in chats.get("list", []):
    print(chat.get("chatId"), chat.get("profile", {}).get("name"))
```

`getChats()` の `limit` はLINE側APIの制約により1〜25です。省略時は25件を取得します。

## 初回ログイン

保存Cookieがまだない場合は、可視Chromeを使う次のコードが基本です。パスワードは画面へ表示されない `getpass()` で受け取ります。

```python
from getpass import getpass

from LINELib import LineBot


def request_email_otp() -> str:
    return input("メールに届いた6桁のログインコード: ").strip()


bot = LineBot(
    cookie_path="lineoa-storage.json",
    email=input("LINE Business IDのメールアドレス: ").strip(),
    password=getpass("LINE Business IDのパスワード: "),
    get_2fa_code_callback=request_email_otp,
    interactive_login=True,
)
print(bot.getBots())
```

`browser_channel` の既定値は `chrome` です。Edgeを使う場合だけ `browser_channel="msedge"` を追加します。reCAPTCHAは公式ログインページ内で実行され、視覚的な確認が出たときだけブラウザ上で操作します。メールOTPが不要なアカウントではcallbackは呼ばれません。

成功すると `lineoa-storage.json` にCookieが保存されます。以後はメールアドレスとパスワードを渡さずに再利用できます。

```python
from LINELib import LineBot

bot = LineBot(cookie_path="lineoa-storage.json")
```

認証方式と安全上の注意は[認証](authentication.md)を参照してください。

## テキストを送信する

```python
from LINELib import LineBot

bot = LineBot(cookie_path="lineoa-storage.json")
result = bot.sendMessage(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    text="Hello from LINELib!",
)
print(result)
```

成功時は通常 `{}` が返ります。ローカルレート制限に達した場合は例外ではなく `{"ratelimit": True, "ratelimit_after": UNIX timestamp}` が返るため、必要なら分岐してください。

```python
if result.get("ratelimit"):
    print("制限解除予定時刻:", result["ratelimit_after"])
```

## イベントを受信する

```python
import os

from LINELib import LineBot

bot = LineBot(cookie_path="lineoa-storage.json")


@bot.event
def on_message(event):
    message = bot.normalize_message_event(event)
    print(message.get("message_type"), message.get("text"))


try:
    bot.listen(botid=os.environ["LINEOA_BOT_ID"])
finally:
    bot.close()
```

`listen()` は既定で処理をブロックし、`Ctrl+C` で停止します。最終終了時は `close()` でPollingと認証済みHTTP Sessionの両方を閉じてください。イベント種別、バックグラウンド実行、再接続は[イベントとPolling](events-and-polling.md)を参照してください。

## 推奨する設定方法

認証情報やIDをソースへ直接書かず、環境変数から読み込みます。PowerShellの現在のプロセスだけに設定する例:

```powershell
$env:LINEOA_EMAIL = "your-email@example.com"
$env:LINEOA_PASSWORD = "your-password"
$env:LINEOA_BOT_ID = "Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
$env:LINEOA_CHAT_ID = "Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

`.env` はLINELib自身では自動読込しません。利用側で `python-dotenv` などを使う場合も、`.env` とCookieファイルをGit管理から除外してください。

## 実行可能なexample

各exampleはリポジトリのルートから実行してください。`example/_login.py` が共通認証処理で、直接実行するファイルではありません。

| ファイル | 内容 | 主な必須環境変数 |
|---|---|---|
| `example_login_edge.py` | Edgeを明示した初回対話ログイン | 未設定ならメールとパスワードを対話入力 |
| `example_send_text.py` | テキスト送信 | `LINEOA_BOT_ID`, `LINEOA_CHAT_ID` |
| `sendfile.py` | ファイル送信 | `LINEOA_BOT_ID`, `LINEOA_CHAT_ID`, `LINEOA_FILE_PATH` |
| `example_send_flex.py` | カード型Flexの作成と送信 | `LINEOA_BOT_ID`, `LINEOA_CHAT_ID`, `LINEOA_AT_ID` |
| `example_polling.py` | SSE Pollingと自動応答、メディア保存 | `LINEOA_BOT_ID` |
| `example_async.py` | asyncテキスト／ファイル送信 | `LINEOA_BOT_ID`, `LINEOA_CHAT_ID` |
| `example_media_save.py` | 保存済みイベントJSONの正規化と保存 | `LINEOA_EVENT_JSON` |
| `example_hybrid.py` | ローカルHTTP callbackとSSEの併用 | `LINEOA_BOT_ID` |

共通の任意環境変数:

| 変数 | 既定値 | 用途 |
|---|---|---|
| `LINEOA_COOKIE_PATH` | `lineoa-storage.json` | Cookie保存先 |
| `LINEOA_EMAIL` | なし | Cookie失効時または初回ログインのメールアドレス |
| `LINEOA_PASSWORD` | なし | Cookie失効時または初回ログインのパスワード |
| `LINEOA_BROWSER_CHANNEL` | `chrome` | `chrome` または `msedge` |
| `LINEOA_INTERACTIVE_TIMEOUT` | `300` | 対話ログイン待機秒数 |
| `LINEOA_FILE_PATH` | exampleによる | 送信ファイル。async例では任意 |

`example/_login.py` は、メールとパスワードが両方あるときだけ対話ログインを有効化します。片方だけ設定すると誤設定として `RuntimeError` になります。保存Cookieが有効なら、認証情報が設定されていてもCookieが優先されます。

`example_hybrid.py` のHTTPサーバーは `127.0.0.1:6100` のローカル確認用です。Messaging APIのWebhook署名検証を実装していないため、そのまま公開しないでください。

## 次に読む

- 送信・取得・保存を増やす: [メッセージとメディア](messages-and-media.md)
- 受信処理を作る: [イベントとPolling](events-and-polling.md)
- 全引数を確認する: [LineBot API](linebot-api.md)
- 問題が起きた: [トラブルシューティング](troubleshooting.md)
