# LINELib

> LINE公式アカウントのチャット操作を行う非公式Pythonラッパー

[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

> [!WARNING]
> 本ライブラリはLINEの非公式Webエンドポイントを利用します。
> LINEの利用規約・仕様変更により動作しなくなる可能性があります。
> 自己責任のもとでご利用ください。

---

## 目次

- [概要](#概要)
- [機能一覧](#機能一覧)
- [インストール](#インストール)
- [クイックスタート](#クイックスタート)
- [認証・ログイン](#認証ログイン)
- [メッセージ送信](#メッセージ送信)
  - [テキスト送信](#テキスト送信)
  - [ファイル送信](#ファイル送信)
  - [メンション送信](#メンション送信)
  - [Flexメッセージ送信](#flexメッセージ送信)
- [イベント受信](#イベント受信)
  - [ハンドラ登録](#ハンドラ登録)
  - [イベント構造](#イベント構造)
- [listen / stop](#listen--stop)
- [既読をつける](#既読をつける)
- [レート制限](#レート制限)
- [チャット・Bot情報取得](#チャットbot情報取得)
- [非同期API](#非同期api)
- [クラスリファレンス](#クラスリファレンス)
- [設定リファレンス](#設定リファレンス)
- [エラーハンドリング](#エラーハンドリング)
- [テスト](#テスト)
- [ライセンス](#ライセンス)

---

## 概要

LINELib は `chat.line.biz` / `manager.line.biz` のWeb APIをPythonから操作するためのライブラリです。  
LINE Messaging API（公式SDK）とは独立しており、**チャット画面上での手動操作を自動化する**ことを目的としています。

```
LINELib
├── LineBot          高レベルBotクラス（推奨エントリーポイント）
├── LINELib          セッション管理・送受信ラッパー
├── ChatService      チャットAPIの生通信層
├── AuthService      Cookieログイン / Seleniumログイン
├── ListenConfig     SSE接続設定
├── RateLimitConfig  レート制限設定
└── LINEOAError      例外クラス
```

---

## 機能一覧

| 機能 | 説明 |
|------|------|
| Cookie再利用 | 保存済みCookieでセッション復元 |
| Seleniumログイン | 初回のみブラウザ起動でログイン・Cookie保存 |
| テキスト送信 | チャットへテキストメッセージを送信 |
| ファイル送信 | 画像・ファイルをアップロード送信 |
| メンション送信 | ユーザーへのメンション送信 |
| Flex送信 | カードメッセージの動的作成・送信・削除 |
| 既読 | チャットを既読にする |
| イベント受信 | SSEによるリアルタイムイベント受信 |
| 自動再接続 | lastEventIdを引き継いだ再接続 |
| レート制限 | ローカルでの送信頻度制御 |
| 非同期送信 | aiohttp対応の async/await API |
| チャット情報取得 | Bot一覧・チャット一覧・メンバー取得 |

---

## インストール

```bash
pip install lineoa
```

開発用（ソースから）:

```bash
git clone https://github.com/yourname/LINELib.git
cd LINELib
pip install -e .
```

依存パッケージ:

```
requests
aiohttp
selenium
```

---

## クイックスタート

```python
from LINELib import LineBot

bot = LineBot(cookie_path="lineoa-storage.json")

bot.sendMessage(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    text="Hello from LINELib!",
)
```

初回実行時はSeleniumがブラウザを起動してログイン・Cookie保存を行います。  
2回目以降は `lineoa-storage.json` が自動で読み込まれます。

---

## 認証・ログイン

### Cookie自動復元

`lineoa-storage.json` が存在する場合、自動でCookieを読み込んでセッションを復元します。

```python
bot = LineBot(cookie_path="lineoa-storage.json")
```

### Seleniumによる初回ログイン

Cookieが存在しない・無効な場合は `email` / `password` を指定するとSeleniumで自動ログインします。

```python
bot = LineBot(
    cookie_path="lineoa-storage.json",
    email="your@email.com",
    password="yourpassword",
)
```

> [!CAUTION]
> `lineoa-storage.json` には認証Cookieが平文で保存されます。
> `.gitignore` に追加してリポジトリに含めないようにしてください。

```gitignore
lineoa-storage.json
```

---

## メッセージ送信

### テキスト送信

```python
bot.sendMessage(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    text="こんにちは",
)
```

引用返信（`quoteToken` 指定）:

```python
bot.sendMessage(
    bot_id=bot_id,
    chat_id=chat_id,
    text="返信です",
    quoteToken="xxxxxxxx",
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

### メンション送信

```python
bot._lib.send_mention(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    mentionee_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
)
```

### Flexメッセージ送信

`chat.line.biz` の仕様上、Flex JSONを直接送信することはできません。  
LINELibでは **カードを動的作成 → 送信 → 削除** のフローで動的Flexを実現しています。

#### `create_and_send_flex` — 作成・送信・削除を一括実行

```python
bot._lib._chat_service.create_and_send_flex(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",  # BotのUID
    at_id="318ogzps",                            # Botの@ID（@なし）
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", # 送信先チャットID
    title="商品名",
    image_url="https://example.com/image.jpg",
    tag_name="NEW",          # タグテキスト（空文字で非表示）
    tag_color="info",        # info / success / warning / danger
    description="説明文",
    action_label="詳しく見る",
    action_text="詳しく見る",  # ボタン押下時に送信されるテキスト
    delete_after_send=True,    # 送信後にカードを自動削除（デフォルト: True）
    session=bot._session,
    xsrf_token=bot._xsrf_token,
)
```

#### 個別API

カードの作成・削除を個別に制御したい場合:

```python
# カード作成 → ID取得
card_id = bot._lib._chat_service.create_card_type_message(
    at_id="318ogzps",
    title="商品名",
    image_url="https://example.com/image.jpg",
    tag_name="SALE",
    tag_color="danger",
    description="期間限定セール中",
    action_label="購入する",
    action_text="購入する",
    session=bot._session,
    xsrf_token=bot._xsrf_token,
)

# 送信
bot._lib._chat_service.send_flex_message(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    card_type_message_id=card_id,
    session=bot._session,
    xsrf_token=bot._xsrf_token,
)

# 削除
bot._lib._chat_service.delete_card_type_message(
    at_id="318ogzps",
    card_id=card_id,
    session=bot._session,
    xsrf_token=bot._xsrf_token,
)
```

#### 既存カードの一覧取得

OA Managerで作成済みのカードIDを取得する場合:

```python
import requests, json

with open("lineoa-storage.json") as f:
    data = json.load(f)

session = requests.Session()
for c in data["cookies"]:
    session.cookies.set(c["name"], c["value"], domain=c.get("domain"))

resp = session.get(
    f"https://chat.line.biz/api/v1/bots/{BOT_ID}/cardTypeMessages",
    headers={"Accept": "application/json"},
)
cards = resp.json().get("list", [])
for card in cards:
    print(card["id"], card["title"])
```

---

## イベント受信

### ハンドラ登録

`@bot.event` デコレータで関数名をイベント名として登録します。

```python
@bot.event
def on_message(event):
    payload      = event.get("payload", {})
    chat_payload = payload.get("payload", {})
    message      = chat_payload.get("message", {})

    chat_id = chat_payload.get("chatId")
    bot_id  = chat_payload.get("botId")
    text    = message.get("text", "")

    if text == "ping":
        bot.sendMessage(bot_id=bot_id, chat_id=chat_id, text="pong")
```

未登録のイベントタイプを受け取りたい場合:

```python
@bot.event
def on_unknown(event):
    print("unknown event:", event)
```

### イベント構造

受信するイベントの基本構造:

```python
{
    "id": "イベントID（lastEventId）",
    "type": "イベントタイプ",
    "payload": {
        "subEvent": "message",       # message / read / delivery など
        "botId": "Uxxxxxxxx",
        "chatId": "Uxxxxxxxx",
        "payload": {
            "type": "message",
            "message": {
                "id": "メッセージID",
                "type": "text",
                "text": "メッセージ本文",
                "createdAt": 1710000000000,  # ミリ秒タイムスタンプ
            }
        }
    },
    "time": "18:00:00.000"
}
```

---

## listen / stop

### 同期リスニング（ブロッキング）

```python
bot.listen(botid="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
# Ctrl+C で停止
```

### 非同期リスニング（ノンブロッキング）

```python
thread = bot.listen(botid="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", block=False)

# メインスレッドで他の処理
time.sleep(60)

bot.stop()
thread.join()
```

### 自動再接続

SSEが切断・例外発生した場合、`reconnect_interval` 秒待機後に自動再接続します。  
`lastEventId` を引き継ぐためイベントの取りこぼしを最小化します。

```python
bot = LineBot(
    cookie_path="lineoa-storage.json",
    reconnect_interval=5,   # 再接続待機秒数（デフォルト: 5）
    max_reconnects=None,    # 最大再接続回数（None=無制限）
)
```

---

## 既読をつける

```python
bot._lib._chat_service.mark_as_read(
    bot_id=bot_id,
    chat_id=chat_id,
    message_id="618399830900998145",
    timestamp=1781426326503,          # 省略時は現在時刻（ミリ秒）
    session=bot._session,
    xsrf_token=bot._xsrf_token,
)
```

イベントハンドラ内での典型的な使い方:

```python
@bot.event
def on_message(event):
    payload      = event.get("payload", {})
    chat_payload = payload.get("payload", {})
    msg          = chat_payload.get("message", {})
    msg_id       = msg.get("id")
    msg_ts       = msg.get("createdAt")

    if msg_id:
        bot._lib._chat_service.mark_as_read(
            bot_id=chat_payload.get("botId"),
            chat_id=chat_payload.get("chatId"),
            message_id=msg_id,
            timestamp=int(msg_ts) if msg_ts else None,
            session=bot._session,
            xsrf_token=bot._xsrf_token,
        )
```

---

## レート制限

ローカルで送信頻度を管理し、LINEサーバー側のレート制限に引っかかるのを防ぎます。

```python
bot = LineBot(
    cookie_path="lineoa-storage.json",
    rate_limit=18,           # ウィンドウ内の最大送信回数（デフォルト: 18）
    rate_limit_window=60,    # ウィンドウ秒数（デフォルト: 60）
    rate_limit_enabled=True, # 有効/無効（デフォルト: True）
)
```

### 状態確認

```python
status = bot.getRateLimitStatus()
print(status)
# {
#     "limited": False,
#     "count": 3,
#     "limit": 18,
#     "window": 60.0,
#     "enabled": True,
#     "ratelimit_after": 0,
# }
```

### リセット

```python
bot.resetRateLimit()
```

### レート制限時のレスポンス

送信がブロックされた場合、送信関数は以下を返します（例外は発生しません）:

```python
{
    "ratelimit": True,
    "ratelimit_after": 1710000060.0,  # 解除されるUNIXタイムスタンプ
}
```

> [!NOTE]
> これはローカルの安全機能です。LINEサーバー側の制限とは独立しています。

---

## チャット・Bot情報取得

### Bot一覧

```python
bots = bot.getBots()
print(bots)
# BotsInfo(6 bots)
#   SB-moi : Uxxxxxxxx (@318ogzps)
#   ...

# IDマップ取得
ids = bots.ids   # {"@318ogzps": "Uxxxxxxxx", ...}
```

### チャット一覧

```python
chats = bot.getChats(bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
print(chats)
# ChatsInfo(10 chats)
#   田中太郎 : Uxxxxxxxx  [USER]
#   営業チーム : Cxxxxxxxx [GROUP]

# ユーザーチャットIDのリスト
user_ids  = chats.user.ids   # ["Uxxxxxxxx", ...]
group_ids = chats.group.ids  # ["Cxxxxxxxx", ...]
```

### メッセージ履歴取得

```python
messages = bot.getChatMessages(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    limit=50,
    before=None,   # このメッセージIDより前を取得
    after=None,    # このメッセージIDより後を取得
)
```

### チャットメンバー取得

```python
members = bot.getMembers(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Cxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    limit=100,
)
```

---

## 非同期API

`async/await` での送信に対応しています。

### テキスト送信（非同期）

```python
import asyncio

async def main():
    await bot._lib.async_send_message(
        user_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        context="hello async",
        bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    )

asyncio.run(main())
```

### ファイル送信（非同期）

```python
async def main():
    await bot._lib.async_send_file(
        chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        file_path="./image.png",
        bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    )
```

---

## クラスリファレンス

### `LineBot`

高レベルBotクラス。通常はこれだけを使います。

| メソッド | 説明 |
|----------|------|
| `sendMessage(bot_id, chat_id, text, quoteToken=None)` | テキスト送信 |
| `sendFile(bot_id, chat_id, file_path)` | ファイル送信 |
| `getChatMessages(bot_id, chat_id, limit, before, after)` | メッセージ履歴取得 |
| `getMembers(bot_id, chat_id, limit)` | チャットメンバー取得 |
| `getBots()` | Bot一覧取得 |
| `getChats(bot_id, limit)` | チャット一覧取得 |
| `getRateLimitStatus()` | レート制限状態確認 |
| `resetRateLimit()` | レート制限カウンターリセット |
| `listen(botid, block=True)` | SSEリスニング開始 |
| `stop()` | リスニング停止 |
| `event(func)` | イベントハンドラ登録デコレータ |

### `ChatService`

低レベルAPI通信層。直接使う場合は `bot._lib._chat_service` 経由でアクセスします。

| メソッド | 説明 |
|----------|------|
| `send_message(bot_id, chat_id, message, session, xsrf_token)` | メッセージ送信（raw） |
| `send_file(bot_id, chat_id, file_path, session, xsrf_token)` | ファイル送信 |
| `send_mention(bot_id, chat_id, mentionee_id, session, xsrf_token)` | メンション送信 |
| `send_flex_message(bot_id, chat_id, card_type_message_id, session, xsrf_token)` | Flex送信 |
| `create_card_type_message(at_id, title, image_url, ...)` | カード作成 |
| `delete_card_type_message(at_id, card_id, session, xsrf_token)` | カード削除 |
| `create_and_send_flex(bot_id, at_id, chat_id, title, image_url, ...)` | Flex一括送信 |
| `mark_as_read(bot_id, chat_id, message_id, timestamp, session, xsrf_token)` | 既読 |
| `get_chat_messages(bot_id, chat_id, session, xsrf_token, limit, before, after)` | メッセージ履歴 |
| `get_chat_members(bot_id, chat_id, limit, session, xsrf_token)` | メンバー取得 |
| `get_bot_accounts(session, xsrf_token, limit, no_filter)` | Bot一覧 |
| `get_chats(bot_id, session, xsrf_token, limit)` | チャット一覧 |
| `get_streaming_api_token(bot_id, session, xsrf_token)` | SSEトークン取得 |
| `stream_events(streaming_api_token, ...)` | SSEイベントストリーム（Generator） |
| `set_typing(bot_id, chat_id)` | タイピング表示 |

### `LINELib`

セッション管理・送受信ラッパー。`bot._lib` でアクセスできます。

| プロパティ / メソッド | 説明 |
|----------------------|------|
| `bots` | `BotsInfo` オブジェクト |
| `chats` | `ChatsInfo` オブジェクト |
| `_session` | `requests.Session` |
| `_xsrf_token` | XSRFトークン |
| `send_message(user_id, context, bot_id, quoteToken)` | テキスト送信 |
| `send_file(chat_id, file_path, bot_id)` | ファイル送信 |
| `send_mention(bot_id, chat_id, mentionee_id)` | メンション送信 |
| `check_rate_limit()` | レート制限状態 |
| `reset_rate_limit()` | レート制限リセット |
| `get_bots()` | Bot一覧 |
| `get_chats(bot_id, limit)` | チャット一覧 |

### `LINEOAError`

すべての例外の基底クラス。

```python
from LINELib import LINEOAError

try:
    bot.sendMessage(...)
except LINEOAError as e:
    print(e)           # メッセージ
    print(e.code)      # エラーコード（任意）
    print(e.details)   # 詳細（任意）
```

---

## 設定リファレンス

### `LineBot.__init__` パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `cookie_path` | `str` | `"lineoa-storage.json"` | Cookie保存パス |
| `email` | `str \| None` | `None` | ログイン用メールアドレス |
| `password` | `str \| None` | `None` | ログイン用パスワード |
| `ping_secs` | `int` | `60` | SSE ping間隔（秒） |
| `device_type` | `str` | `""` | デバイスタイプ |
| `client_type` | `str` | `"PC"` | クライアントタイプ |
| `rate_limit` | `int` | `18` | ウィンドウ内最大送信回数 |
| `rate_limit_window` | `float` | `60` | レート制限ウィンドウ（秒） |
| `rate_limit_enabled` | `bool` | `True` | レート制限の有効/無効 |
| `reconnect_interval` | `float` | `5` | 再接続待機秒数 |
| `max_reconnects` | `int \| None` | `None` | 最大再接続回数（None=無制限） |

---

## エラーハンドリング

ハンドラ内で例外が発生しても他のイベント処理は継続します。

```python
@bot.event
def on_message(event):
    try:
        # 処理
    except LINEOAError as e:
        print(f"LINE APIエラー: {e}")
    except Exception as e:
        print(f"予期しないエラー: {e}")
```

ハンドラのエラーはログに記録されます:

```
[2026-06-14 18:00:00] [ERROR] [ERROR] handler error (on_message): HTTP 400: {}
```

---

## テスト

```bash
python -m unittest discover -s tests
```

テスト内容:

- レート制限ロジックの検証
- SSEパーサーの検証

> LINEへの実際の接続は行いません。

---

## ライセンス

[MIT](LICENSE)

---

> 本ライブラリはLINE社とは無関係の非公式プロジェクトです。
