# LINELib

LINELib は、LINE公式アカウントのWebチャット操作を行うための非公式Pythonラッパーです。

認証済みCookieの再利用、チャット・メッセージAPI、ファイル送信、SSEによるメッセージ受信、ローカルでのレート制限や再接続処理を主な機能としています。

※ このライブラリはLINEのWebエンドポイントとSeleniumによるログイン処理を利用します。
利用規約や運用上のリスクを理解した環境でのみ使用してください。

--------------------------------------------------
主な機能
--------------------------------------------------

- Cookieを利用したセッション復元
- Seleniumによる初回ログイン
- Botアカウント・チャット一覧取得
- テキスト送信、メンション送信、ファイル送信
- 同期・非同期送信向けローカルレート制限
- SSE（Server-Sent Events）によるイベント受信
- lastEventId を利用した自動再接続
- listen(block=False) と stop() による安全な制御
- リスナー・レート制限・SSE関連の補助機能

--------------------------------------------------
インストール
--------------------------------------------------

pip install lineoa

開発用インストール:

pip install -e .

--------------------------------------------------
クイックスタート
--------------------------------------------------

```python
from LINELib.linebot import LineBot

bot = LineBot(
    cookie_path="lineoa-storage.json",
    ping_secs=20,
    rate_limit=18,
    rate_limit_window=60,
)

BOT_ID = "Uxxxxxxxx"
CHAT_ID = "xxxxxxxx"

bot.sendMessage(
    bot_id=BOT_ID,
    chat_id=CHAT_ID,
    text="hello"
)
```

初回実行時はSeleniumがブラウザを起動し、
ログインしてCookieを保存する場合があります。

2回目以降は保存済みCookieが利用されます。

--------------------------------------------------
レート制限
--------------------------------------------------

ライブラリは送信履歴を保存し、
設定された制限を超える送信を防ぎます。

```python
bot = LineBot(
    cookie_path="lineoa-storage.json",
    rate_limit=18,
    rate_limit_window=60,
    rate_limit_enabled=True,
)

status = bot.getRateLimitStatus()
print(status)

bot.resetRateLimit()
```

送信がブロックされた場合:

```json
{
    "ratelimit": True,
    "ratelimit_after": 1710000000.0,
    "limit": 18,
    "window": 60.0,
}
```

※ この制限はローカル側の安全機能であり、
LINEサーバー側での送信成功を保証するものではありません。

--------------------------------------------------
イベント受信
--------------------------------------------------

```python
from LINELib.linebot import LineBot

bot = LineBot(
    cookie_path="lineoa-storage.json",
    ping_secs=20,
    reconnect_interval=5,
    max_reconnects=None,
)

@bot.event
def on_message(event):
    payload = event.get("payload", {})
    chat_payload = payload.get("payload", {})
    message = chat_payload.get("message", {})
    text = message.get("text", "")

    if message.get("type") == "text" and text == "ping":
        bot.sendMessage(
            bot_id=payload.get("botId"),
            chat_id=payload.get("chatId"),
            text="pong",
        )

bot.listen(botid="Uxxxxxxxx")
```

--------------------------------------------------
再接続機能
--------------------------------------------------

listen() は以下の場合に自動再接続します。

- SSE接続が切断された場合
- 例外が発生した場合

最後に受信したイベントIDを記録し、
再接続時に引き継ぎます。

--------------------------------------------------
非同期リスニング
--------------------------------------------------

```python
thread = bot.listen(
    botid="Uxxxxxxxx",
    block=False
)
```

# 他の処理

```python
bot.stop()
thread.join()
```
stop() を呼び出すことで安全に終了できます。

--------------------------------------------------
ファイル送信
--------------------------------------------------

```python
bot.sendFile(
    bot_id="Uxxxxxxxx",
    chat_id="xxxxxxxx",
    file_path="sample.png",
)
```

--------------------------------------------------
非同期送信
--------------------------------------------------

```python
await bot._lib.async_send_message(
    user_id="xxxxxxxx",
    context="hello async",
    bot_id="Uxxxxxxxx",
)
```

--------------------------------------------------
主なクラス
--------------------------------------------------

LineBot
    高レベルBotクラス

LINELib
    認証セッション管理

ChatService
    LINEチャットAPI通信

AuthService
    Seleniumログイン管理

RateLimitConfig
    レート制限設定

ListenConfig
    リスナー設定

SSEParser
    SSE解析

SSEEvent
    SSEイベントオブジェクト

--------------------------------------------------
セキュリティ注意事項
--------------------------------------------------

- lineoa-storage.json には認証Cookieが保存されます
- GitHub等へ公開しないでください
- デフォルト設定は保守的です（60秒間に18回送信）
- コールバックエラーは他の処理へ影響しません
- ネットワークエラー時は自動再接続されます
- LINE側の仕様変更により動作しなくなる可能性があります

--------------------------------------------------
テスト実行
--------------------------------------------------
```bash
python -m unittest discover -s tests
```
テスト内容:
- レート制限の検証
- SSEパーサーの検証

※ LINEサーバーへの接続は行いません

--------------------------------------------------
ライセンス
--------------------------------------------------

MITライセンス
