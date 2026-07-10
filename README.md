# LINELib

LINE Official Account の `chat.line.biz` / `manager.line.biz` を Python から扱うためのライブラリです。

この README は、今の実装に合わせた使い方のドキュメントとして読めるように整理しています。

## 概要

LINELib でできること:

- 送信
- 受信
- SSE polling
- 画像 / 動画 / ファイルの保存
- ステッカー画像の保存
- link メッセージの JSON 保存
- 管理系 API の取得

## インストール

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

最初に Cookie ベースでログイン済みの状態を用意するのが基本です。

```python
from LINELib import LineBot

bot = LineBot(cookie_path="lineoa-storage.json")
```

Cookie がない場合は `email` / `password` を渡してログインを試みます。

```python
bot = LineBot(
    cookie_path="lineoa-storage.json",
    email="your@email.com",
    password="yourpassword",
)
```

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
- `on_media`
- `on_unknown`

`on_media` は `image` / `video` / `file` / `audio` / `sticker` / `link` をまとめて扱う入口です。

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

### 非同期実行

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
2. `streaming/state` を `{"connectionId": "...", "idle": true}` で送信
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
bot._lib._chat_service.save_sticker_image(
    sticker_id="123456789",
    file_path="./sticker.png",
    session=bot._session,
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
| `payload` | JSON パース済み payload |
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
import time

from LINELib import LineBot

BOT_ID = os.environ["LINEOA_BOT_ID"]
bot = LineBot(cookie_path=os.environ.get("LINEOA_COOKIE_PATH", "lineoa-storage.json"), ping_secs=30, max_stream_seconds=7200)

@bot.event
def on_message(event):
    normalized = bot.normalize_message_event(event)
    if normalized.get("message_type") == "text" and normalized.get("text") == "ping":
        bot.sendMessage(bot_id=normalized["bot_id"], chat_id=normalized["chat_id"], text="pong")
    if normalized.get("kind") == "media":
        bot.save_message_media(event, f"./outputs/{normalized['message_id']}")

bot.listen(botid=BOT_ID)
while True:
    time.sleep(1)
```

### ステッカー保存

```python
@bot.event
def on_media(event):
    normalized = event.get("normalized", {})
    if normalized.get("message_type") == "sticker":
        bot.save_message_media(event, f"./outputs/{normalized['message_id']}")
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
from LINELib.LINELib import LINELib

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

- `example_send_text.py`
- `sendfile.py`
- `example_send_flex.py`
- `example_polling.py`
- `example_async.py`
- `example_hybrid.py`
- `example_media_save.py`

実行前に必要な環境変数:

- `LINEOA_COOKIE_PATH`
- `LINEOA_BOT_ID`
- `LINEOA_CHAT_ID`
- `LINEOA_AT_ID`
- `LINEOA_FILE_PATH`
- `LINEOA_EVENT_JSON`

## ライセンス

[MIT](LICENSE)
