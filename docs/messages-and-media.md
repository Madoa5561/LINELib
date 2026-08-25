# メッセージとメディア

通常の操作には `LineBot` を使います。このページの `bot` は、認証済みCookieで次のように作成済みとします。

```python
from LINELib import LineBot

bot = LineBot(cookie_path="lineoa-storage.json")
```

## IDの使い分け

| 引数 | 内容 |
|---|---|
| `bot_id` | 送信元となるOfficial AccountのID |
| `chat_id` | 送信先チャットのID。1対1とグループの両方で使用 |
| `mentionee_id` | メンション対象ユーザーのID |
| `at_id` | Official Accountの `basicSearchId`。カード型Flexの作成で使用 |

`bot_id` を省略できるメソッドは、取得できたBot一覧から `responseMode=BOT` を除いた最初のチャット対応Botを使用します。Botモードのアカウントは手動チャットAPIが403になるため、既定候補にはなりません。複数のチャット対応アカウントを管理している場合は、意図しないアカウントを避けるため明示してください。

## テキスト送信

```python
result = bot.sendMessage(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    text="Hello from LINELib!",
)
```

`LineBot.sendMessage()` の引数は `(bot_id, chat_id, text, quoteToken=None)` です。中間層の `LINELib.sendMessage()` は互換aliasで、引数が `(user_id, text, bot_id=None, quoteToken=None)` と異なります。クラスを切り替える場合は位置引数を避け、名前付き引数を使用してください。

成功時の戻り値は通常 `{}` です。HTTPエラーは `LINEOAError`、ローカルレート制限は `{"ratelimit": True, "ratelimit_after": UNIX timestamp}` です。

## 返信付き送信

受信メッセージに含まれる `quoteToken` を渡します。

```python
result = bot.sendMessage(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    text="返信します",
    quoteToken="received-quote-token",
)
```

正規化形式は現在 `quoteToken` を独立フィールドへ移さないため、必要な場合は受信イベントの `normalized["raw"]` または元のイベントから取得してください。

## ファイル送信

```python
result = bot.sendFile(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    file_path="./image.png",
)
```

ファイルをアップロードして `contentMessageToken` を取得し、そのtokenを使って送信します。ファイルが存在しない場合、uploadまたは送信が失敗した場合はいずれも `LINEOAError` になります。

## メンション送信

`LineBot` はメンションの直接wrapperを公開していません。中間層の `LINELib` を使用します。

```python
from LINELib import LINELib

lib = LINELib(storage="lineoa-storage.json")
result = lib.send_mention(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    mentionee_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
)
```

互換alias `sendMention()` もあります。新しいコードではsnake_caseの `send_mention()` を推奨します。

## カード型Flex

この実装のFlexはMessaging APIの任意Flex JSONを直接送る機能ではありません。Manager APIでカード型メッセージを一時作成し、作成された `cardTypeMessageId` をチャットへ送信する処理です。

```python
card_id = bot.create_and_send_flex(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    at_id="@example",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    title="お知らせ",
    image_url="https://example.com/image.jpg",
    tag_name="NEW",
    tag_color="info",
    description="説明文",
    action_label="開く",
    action_text="詳細を見る",
    delete_after_send=True,
)
print(card_id)
```

戻り値は作成されたカードIDです。ローカルレート制限中は戻り値の型を変えず、`LINEOAError(code="rate_limited")` を送出します。`delete_after_send` は真偽値で指定してください。`True` では送信後にManager側の一時カードを削除しますが、送信済みメッセージを取り消す指定ではありません。

送信成功後に一時カードの削除だけが失敗した場合は、`LINEOAError(code="flex_cleanup_failed")` が送出され、`details` は `{"message_sent": True, "card_id": ...}` を含みます。この場合メッセージは送信済みなので、例外を理由にそのまま再送すると重複送信になる可能性があります。`image_url` はLINE側から取得できる公開HTTPS URLを使用してください。

## Bot、チャット、履歴、メンバー

```python
accounts = bot.getBots()
print(accounts.ids)

chats = bot.getChats(bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", limit=25)
messages = bot.getChatMessages(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    limit=50,
)
members = bot.getMembers(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    limit=100,
)
```

- `getBots()` は `BotsInfo` を返し、`.ids` で `{basicSearchIdまたは名前: bot_id}` を取得できます。
- `getChats()` の `limit` は1〜25で、省略時は25です。
- `getChatMessages()` と `getMembers()` の `limit` は1〜100です。
- `getChats()`、`getChatMessages()`、`getMembers()` はLINE内部APIのJSONを `dict` のまま返します。
- `getMembers()` はグループチャット向けです。1対1チャットではLINE側が400を返す場合があります。
- `before` / `after` は履歴APIへ渡すページングカーソルです。LINEのレスポンスに含まれる不透明な文字列を変更せず使用してください。従来互換として正の整数も指定できます。空文字、bool、0、その他の型は通信前に `LINEOAError` になります。
- 内部APIの生レスポンスキーはLINE側の変更対象です。存在確認には `.get()` を使用してください。

## 管理情報の取得

`LineBot` には管理画面関連の取得wrapperがあります。すべて認証済みSessionを使い、基本的にLINE側のJSONを `dict` のまま返します。

| 分類 | メソッド |
|---|---|
| ログイン利用者・Bot | `get_me()`, `get_bot_account()`, `get_csrf_token()` |
| チャット | `get_pinned_messages()`, `get_activities()`, `get_notes()`, `get_use_manual_chat()` |
| Bot設定 | `get_chat_mode()`, `get_chat_mode_schedules()`, `get_available_features()`, `get_banner_web()`, `get_call_session()` |
| 入力支援 | `set_typing()`, `get_recent_stickers()`, `get_recent_emojis()`, `get_saved_replies()` |
| 権限・共通情報 | `get_authorized_users()`, `get_whitelist_domains()`, `get_me_settings_pc()`, `get_plugins()` |
| 時刻・休日 | `get_clock_now()`, `get_holiday()` |

引数の完全な一覧は[LineBot API](linebot-api.md)を参照してください。

## イベントを正規化する

```python
normalized = bot.normalize_message_event(event)
print(normalized.get("message_type"))
print(normalized.get("content_hash"))
print(normalized.get("file_name"))
```

正規化形式の全フィールドは[イベントとPolling](events-and-polling.md#正規化メッセージ)を参照してください。メッセージでないイベントは `{"kind": "unknown", "raw_event": event}` になります。`event` は辞書である必要があり、それ以外はファイル操作や通信より前に `LINEOAError` になります。

## 受信メディアを保存する

```python
saved_path = bot.save_message_media(event, "./outputs/message")
print(saved_path)
```

拡張子を指定しない場合は次のように補完します。

| `message_type` | 既定の拡張子 | 保存内容 |
|---|---|---|
| `image` | `.jpg` | content previewのbytes |
| `video` | `.mp4` | content previewのbytes |
| `file` | 元ファイルの拡張子、なければ `.bin` | content previewのbytes |
| `audio` | `.m4a` | content previewのbytes |
| `sticker` | `.png` | sticker CDNの画像 |
| `link` | `.json` | linkメタデータ |

出力先の親ディレクトリは自動作成され、戻り値は実際の保存パスです。ダウンロード中に通信が切断された場合は部分ファイルを残さず、`LINEOAError` を送出します。

`link` のJSONには次のキーが入ります。

- `message_id`
- `bot_id`
- `chat_id`
- `title`
- `url`
- `text`
- `timestamp`
- `raw`

画像・動画・ファイル・音声に `content_hash` がない場合、ステッカーに `sticker_id` がない場合は `LINEOAError` です。期限切れメディアは `expired` / `expired_at` を確認してください。

## プレビューとステッカーを直接保存する

```python
preview_bytes = bot.get_image_preview(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    content_hash="content-hash",
)

preview_path = bot.save_image_preview(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    content_hash="content-hash",
    file_path="./outputs/preview.jpg",
)

sticker_path = bot.save_sticker_image(
    sticker_id="123456789",
    file_path="./outputs/sticker.png",
)
```

`get_image_preview()` はbytes、2つの `save_*()` は保存パスを返します。メソッド名はimageですが、内部ではcontent preview endpointを使用します。受信イベントからの保存には、種別を判定する `save_message_media()` の方が安全です。必須のID、content hash、保存先が欠けている場合は、通信・ファイル操作前に `LINEOAError` になります。

## ローカルレート制限

`LineBot` の既定値は60秒間に18回です。テキスト、ファイル、メンション、カード型Flexの送信枠をCookie保存先と同じJSONへ記録します。判定と記録はlock内で一括実行されるため、複数スレッド／プロセスからの同時送信でも同じ上限を共有します。`rate_limit_enabled=False` では送信枠を記録しません。

```python
status = bot.getRateLimitStatus()
print(status)

if status["limited"]:
    print(status["ratelimit_after"])
```

戻り値:

| キー | 内容 |
|---|---|
| `limited` | 現在ローカル制限中か |
| `count` | 設定window内の送信記録数 |
| `limit` | 設定上限 |
| `window` | 判定秒数 |
| `enabled` | ローカル判定が有効か |
| `ratelimit_after` | 制限解除予定のUNIX timestamp。制限外は0 |

`resetRateLimit()` はローカル履歴だけを消します。LINE側の制限は解除しません。通常運用での制限回避目的には使用しないでください。

## async API

async機能は `LINELib` にあります。

```python
import asyncio

from LINELib import LINELib


async def main() -> None:
    lib = LINELib(storage="lineoa-storage.json")
    await lib.async_send_message(
        user_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        context="async text",
        bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    )
    await lib.async_send_file(
        chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        file_path="./image.png",
        bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    )


asyncio.run(main())
```

`async_send_message()`、`async_send_file()`、`async_send_mention()` も同じローカルレート制限を使います。`async_get_chat_messages()` は送信履歴を変更しません。内部で作成した `aiohttp.ClientSession` は処理後に閉じます。
