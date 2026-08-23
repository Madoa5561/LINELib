# LINELib

LINE Official Account の `chat.line.biz` / `manager.line.biz` を Python から扱うためのライブラリです。

この README は、今の実装に合わせた使い方のドキュメントとして読めるように整理しています。

> [!IMPORTANT]
> LINEヤフー株式会社の公式SDKではありません。管理画面の内部APIに依存するため、予告なく動かなくなる可能性があります。自分が管理権限を持つOfficial Accountで利用してください。

## 概要

LINELib でできること:

- 送信
- 受信
- SSE polling
- 画像 / 動画 / ファイルの保存
- ステッカー画像の保存
- link メッセージの JSON 保存
- 管理系 API の取得

## ドキュメント

初めて使う場合は、次の順番で読むとライブラリ全体を把握できます。

1. [ドキュメント目次](docs/README.md) - 機能、用語、クラス構成の全体像
2. [はじめに](docs/getting-started.md) - インストールから最初の送受信まで
3. [認証](docs/authentication.md) - Cookie、直接HTTP、Chrome/Edge、OTP
4. [メッセージとメディア](docs/messages-and-media.md) - 送信、取得、保存、Flex
5. [イベントとPolling](docs/events-and-polling.md) - SSE、ハンドラ、正規化形式
6. [LineBot API](docs/linebot-api.md) - 推奨入口の全引数・全公開メソッド
7. [低レベルAPI](docs/low-level-api.md) - LINELib、ChatService、AuthService、SSE
8. [トラブルシューティング](docs/troubleshooting.md) - 症状別の確認方法

迷った場合は、高レベルAPIの `LineBot` を使用してください。`LINELib` はasync APIや細かな制御が必要な場合、`ChatService` / `AuthService` は認証済みSessionを自分で管理する場合の低レベル入口です。

## インストール

Python 3.10 以上が必要です。

```bash
pip install lineoa
```

開発用:

```bash
git clone https://github.com/Madoa5561/LINELib.git
cd LINELib
pip install -e .
```

## セットアップ

最初にCookieベースでログイン済みの状態を用意するのが基本です。

```python
from LINELib import LineBot

bot = LineBot(cookie_path="lineoa-storage.json")
```

`lineoa-storage.json`にはログインCookieが平文で保存されます。Gitへcommitしたり、第三者と共有したりしないでください。保存済みCookieが有効なら、メールアドレスやパスワードを送信せずに再利用します。

### Windows 11 / Google Chromeで初回ログイン

reCAPTCHAを含む初回ログインには、Windowsへインストール済みのGoogle Chromeを使う対話ログインを既定とします。任意依存を追加してください。Playwright自身のChromiumを別途ダウンロードする必要はありません。

```bash
pip install "lineoa[interactive-login]"
```

```python
import os

from LINELib import InteractiveLoginRequired, LineBot

try:
    bot = LineBot(
        cookie_path="lineoa-storage.json",
        email=os.environ["LINEOA_EMAIL"],
        password=os.environ["LINEOA_PASSWORD"],
        get_2fa_code_callback=lambda: input("メールに届いた6桁のログインコード: ").strip(),
        interactive_login=True,
        browser_channel="chrome",
    )
except InteractiveLoginRequired as error:
    print(f"ブラウザでの追加認証が必要です: {error.reason}")
```

`browser_channel`の既定値は`chrome`です。`interactive_login=True`では、保存Cookieの検証後、PythonからログインAPIへ認証情報を事前送信せず、最初から実際のGoogle Chromeで公式ログイン画面を開きます。Microsoft Edgeを使う場合は`browser_channel="msedge"`を指定してください。

User-AgentとClient Hintsは、Windows 11上の可視Chrome/Edgeが公式ログインページへ実際に送信した値へ固定しています。Windows 11でもUA互換仕様によりOS部分は`Windows NT 10.0`になります。ブラウザ内のリクエストと、Cookieを引き継ぐOTP検証・リダイレクト用HTTP Sessionの両方で同じ値を使用します。

- Chrome: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36`
- Edge: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0`

メール2段階認証が必要な場合は、`get_2fa_code_callback` が返した6桁コードを同じログインセッションで検証します。コードをソースやCookieファイルへ保存する必要はありません。

reCAPTCHAはログインコードのように別途入力できる値ではなく、公式ページのブラウザセッション内で実行されます。隠しreCAPTCHAは公式ページ上で通常実行され、視覚的な確認が表示された場合だけ利用者が操作してください。LINELibはCAPTCHAの解読や回避を行いません。

verification画面へ進むと対話ブラウザを閉じ、同じCookieとCSRFを引き継いだHTTPセッションでメールOTPを検証します。成功後のCookieは`cookie_path`へ保存されます。ChromeとEdge以外のchannelは、誤ったUAを送信しないよう拒否します。

### ブラウザを使わない直接HTTPログイン

`interactive_login=False`のまま`email` / `password`を渡すと、ブラウザやSeleniumを使わずLINEヤフーBusiness IDのログインAPIへ直接ログインします。この場合も`browser_channel`に対応する固定UAを送信します。reCAPTCHAが要求されなければそのまま完了し、要求された場合は`InteractiveLoginRequired(reason="recaptcha")`を送出します。認証情報はCookieファイルへ保存されません。

## 基本送信

### テキスト送信

```python
bot.sendMessage(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    text="Hello from LINELib!",
)
```

### ファイル送信

```python
bot.sendFile(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    file_path="./image.png",
)
```

### 返信付き送信

```python
bot.sendMessage(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    text="reply",
    quoteToken="xxxxxxxx",
)
```

## 受信

### イベント登録

```python
@bot.event
def on_message(event):
    print(event)
```

### 使えるイベント名

- `on_init`
- `on_ping`
- `on_message`
- `on_image`
- `on_video`
- `on_file`
- `on_audio`
- `on_sticker`
- `on_link`
- `on_media`
- `on_unknown`

`on_media` は `image` / `video` / `file` / `audio` / `sticker` / `link` をまとめて扱うfallbackです。`on_image` など種別固有のハンドラが登録されている場合は、そちらが先に呼ばれます。完全な優先順位は[イベントとPolling](docs/events-and-polling.md#ハンドラ名と選択順)を参照してください。

### メディアイベントの正規化

```python
@bot.event
def on_media(event):
    normalized = event.get("normalized", {})
    print(normalized["kind"])
    print(normalized["message_type"])
    print(normalized.get("media_url"))
```

## SSE / Polling

### 基本

```python
bot.listen(botid="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
```

### バックグラウンド実行

```python
thread = bot.listen(botid="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", block=False)

import time
time.sleep(60)

bot.stop()
thread.join()
```

### polling の挙動

polling は次の順序で動きます。

1. `streamingApiToken` を取得
2. レスポンスに `connectionId` がある場合だけ、`streaming/state` を `{"connectionId": "...", "idle": true}` で送信
3. `streamingApiBaseUrl` と `streamingApiVersion` に従って SSE 接続
4. `lastEventId` を引き継いで再接続
5. `expiredAt` を見て、期限前に張り替え

HAR に合わせて、`init` と `ping` も通常イベントとして扱えます。

## メディア保存

### 画像

```python
event = ...
bot.save_message_media(event, "./downloaded/image")
```

拡張子なしで渡すと、種別に応じて補完されます。

- `image` -> `.jpg`
- `video` -> `.mp4`
- `file` -> `.bin`
- `audio` -> `.m4a`
- `sticker` -> `.png`
- `link` -> `.json`

### 画像プレビューを直接保存

```python
bot.save_image_preview(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    content_hash="xxxxxxxx",
    file_path="./preview.jpg",
)
```

### ステッカー画像を直接保存

```python
bot.save_sticker_image(
    sticker_id="123456789",
    file_path="./sticker.png",
)
```

### link メッセージの保存

`link` は画像保存ではなく、メタデータ JSON を保存します。

```python
bot.save_message_media(event, "./downloaded/link")
```

保存される JSON には次が入ります。

- `message_id`
- `bot_id`
- `chat_id`
- `title`
- `url`
- `text`
- `timestamp`
- `raw`

## メッセージ正規化

`normalize_message_event()` を使うと、受信イベントを共通構造にできます。

```python
normalized = bot.normalize_message_event(event)
print(normalized["kind"])
print(normalized["message_type"])
print(normalized.get("media_url"))
```

主な `kind`:

- `media`
- `link`
- `sticker`
- `audio`
- `text`
- `unknown`

## 管理系 API

HAR に出てきた管理画面寄りの API もいくつかラッパー化しています。

```python
bot.get_me()
bot.get_whitelist_domains()
bot.get_me_settings_pc()
bot.get_chat_mode(bot_id)
bot.get_chat_mode_schedules(bot_id)
bot.get_available_features(bot_id)
bot.get_banner_web(bot_id)
bot.get_call_session(bot_id)
bot.get_activities(bot_id, chat_id)
bot.get_notes(bot_id, chat_id)
bot.get_authorized_users(bot_id)
bot.get_use_manual_chat(bot_id, chat_id)
bot.get_recent_stickers(bot_id)
bot.get_recent_emojis(bot_id)
bot.get_saved_replies(bot_id)
bot.get_clock_now()
bot.get_holiday("JP")
bot.get_plugins(bot_id)
```

## クラス参照

### `LineBot`

よく使う入口だけをまとめたラッパーです。

| メソッド | 説明 |
|---|---|
| `sendMessage(bot_id, chat_id, text, quoteToken=None)` | テキスト送信 |
| `sendFile(bot_id, chat_id, file_path)` | ファイル送信 |
| `listen(botid, block=True)` | SSE polling 開始 |
| `stop()` | polling 停止 |
| `event(func)` | イベントハンドラ登録 |
| `normalize_message_event(event)` | 受信イベントの正規化 |
| `save_message_media(event, file_path)` | メディア保存 |
| `save_image_preview(bot_id, content_hash, file_path)` | 画像プレビュー保存 |
| `save_sticker_image(sticker_id, file_path)` | ステッカー画像保存 |

### `ChatService`

低レベルの API です。必要なら直接使えます。

| メソッド | 説明 |
|---|---|
| `get_streaming_api_token(bot_id, ...)` | polling 用トークン取得 |
| `stream_events(streaming_api_token, ...)` | SSE 接続 |
| `streaming_state(bot_id, state)` | streaming state 送信 |
| `get_content_preview(bot_id, content_hash, ...)` | 画像/動画/ファイルプレビュー |
| `get_sticker_image(sticker_id, ...)` | ステッカー画像取得 |
| `save_content_preview(bot_id, content_hash, file_path, ...)` | プレビュー保存 |
| `save_sticker_image(sticker_id, file_path, ...)` | ステッカー保存 |

### `SSEEvent`

SSE 1件を表します。

| メソッド | 説明 |
|---|---|
| `payload` | JSON パース済みpayload property |
| `normalized_message()` | メッセージ正規化 |
| `image_url()` | 画像プレビュー URL |

## 例

### 画像イベント保存

```python
@bot.event
def on_media(event):
    normalized = event.get("normalized", {})
    if normalized.get("message_type") == "image":
        bot.save_message_media(event, f"./outputs/{normalized['message_id']}")
```

### ステッカー保存

```python
@bot.event
def on_media(event):
    normalized = event.get("normalized", {})
    if normalized.get("message_type") == "sticker":
        bot.save_message_media(event, f"./outputs/{normalized['message_id']}")
```

### link 保存

```python
@bot.event
def on_media(event):
    normalized = event.get("normalized", {})
    if normalized.get("message_type") == "link":
        bot.save_message_media(event, f"./outputs/{normalized['message_id']}")
```

### 実戦向け polling

```python
import os

from LINELib import LineBot

BOT_ID = os.environ["LINEOA_BOT_ID"]
bot = LineBot(cookie_path=os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json"), ping_secs=30, max_stream_seconds=7200)

@bot.event
def on_message(event):
    normalized = bot.normalize_message_event(event)
    if normalized.get("message_type") == "text" and normalized.get("text") == "ping":
        bot.sendMessage(bot_id=normalized["bot_id"], chat_id=normalized["chat_id"], text="pong")
    if normalized.get("message_type") in {"image", "video", "file", "audio", "sticker", "link"}:
        bot.save_message_media(event, f"./outputs/{normalized['message_id']}")

bot.listen(botid=BOT_ID)
```

### 動画保存

```python
@bot.event
def on_media(event):
    normalized = event.get("normalized", {})
    if normalized.get("message_type") == "video":
        bot.save_message_media(event, f"./outputs/{normalized['message_id']}")
```

### link メタデータ保存

```python
@bot.event
def on_media(event):
    normalized = event.get("normalized", {})
    if normalized.get("message_type") == "link":
        bot.save_message_media(event, f"./outputs/{normalized['message_id']}")
```

### async 送信

```python
import asyncio
from LINELib import LINELib

async def main():
    lib = LINELib(storage="lineoa-storage.json")
    await lib.async_send_message(
        user_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        context="async send",
        bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    )

asyncio.run(main())
```

## テスト

```bash
python -m unittest discover -s tests
```

## Example まとめ

`example/` には、README と同じ内容の実行例を置いてあります。

- `example_login_edge.py`
- `example_send_text.py`
- `sendfile.py`
- `example_send_flex.py`
- `example_polling.py`
- `example_async.py`
- `example_hybrid.py`
- `example_media_save.py`

初回ログイン例はWindows PowerShellで次のように実行します。

```powershell
python .\example\example_login_edge.py
```

メールアドレスを入力後、パスワードは画面へ表示されない入力欄で受け取ります。`LINEOA_EMAIL`と`LINEOA_PASSWORD`が設定済みなら入力を省略できます。Microsoft Edgeが開き、必要ならターミナルでメールOTPの入力待ちになります。成功すると`LINEOA_COOKIE_PATH`または`lineoa-storage.json`へCookieを保存します。以後のexampleは同じCookieを再利用するため、Cookieが有効な間は認証情報を設定しなくても実行できます。

`example_login_edge.py`はEdge初回ログインの引数をすべて明示した自己完結例です。その他の既存exampleは`example/_login.py`の共通認証処理を使います。Cookieが失効していて`LINEOA_EMAIL`と`LINEOA_PASSWORD`が設定されている場合は、既定でChromeログインへ移行します。`LINEOA_BROWSER_CHANNEL=msedge`を設定するとEdgeへ切り替えられます。

`example_hybrid.py`のHTTPサーバーはローカル確認用として`127.0.0.1:6100`だけで待ち受けます。公開Webhookとして使う場合に必要な署名検証は実装していません。

実行前に必要な環境変数:

- `LINEOA_COOKIE_PATH`（任意、既定値: `lineoa-storage.json`）
- `LINEOA_EMAIL` / `LINEOA_PASSWORD`（初回ログインまたはCookie失効時）
- `LINEOA_BROWSER_CHANNEL`（任意、既定値: `chrome`、Edgeは`msedge`）
- `LINEOA_INTERACTIVE_TIMEOUT`（任意、既定値: `300`秒）
- `LINEOA_BOT_ID`
- `LINEOA_CHAT_ID`
- `LINEOA_AT_ID`
- `LINEOA_FILE_PATH`
- `LINEOA_EVENT_JSON`

## ライセンス

[MIT](LICENSE)
