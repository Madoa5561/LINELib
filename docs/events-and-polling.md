# イベントとPolling

`LineBot.listen()` は、Streaming API tokenの取得、SSE接続、イベントの辞書化、ハンドラへの振り分け、切断時の再接続をまとめて行います。

## 最小構成

```python
from LINELib import LineBot

bot = LineBot(cookie_path="lineoa-storage.json")


@bot.event
def on_message(event):
    normalized = bot.normalize_message_event(event)
    print(normalized)


bot.listen(botid="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
```

`@bot.event` は関数名をそのままハンドラ名として登録します。任意の関数名ではなく、`on_message` などの規則に合わせてください。同じ名前を再登録すると後の関数で置き換わります。

## SSEイベント辞書

ハンドラへ渡る基本形式:

```python
event = {
    "id": "last-event-id",
    "type": "event-name",
    "payload": {},
    "time": "12:34:56.789",
}
```

`id` は再接続時の `lastEventId`、`type` はSSEのevent名、`payload` はdata行をJSONとして解析した値です。`time` は受信時にローカルで追加される時刻文字列です。LINE側のevent構造は変更される可能性があります。

メッセージと判断できた場合、`LineBot.dispatch()` はさらに `event["normalized"]` を追加してからハンドラを呼びます。

## ハンドラ名と選択順

固定的に使いやすいハンドラ:

| ハンドラ | 呼ばれる条件 |
|---|---|
| `on_init` | SSE event typeが `init` |
| `on_ping` | SSE event typeが `ping` |
| `on_message` | メッセージ全般のfallback |
| `on_image` | 正規化後の `message_type == "image"` |
| `on_video` | `message_type == "video"` |
| `on_file` | `message_type == "file"` |
| `on_audio` | `message_type == "audio"` |
| `on_sticker` | `message_type == "sticker"` |
| `on_link` | `message_type == "link"` |
| `on_media` | image / video / file / audio / sticker / linkの共通fallback |
| `on_unknown` | どのハンドラにも一致しない場合 |

振り分けは次の優先順位です。最初に見つかった1つだけが実行されます。

1. `init` / `ping` の専用ハンドラ
2. `on_{message_type}`
3. 対象種別なら `on_media`
4. メッセージと判定できれば `on_message`
5. `payload.subEvent` があれば `on_{subEvent}`
6. SSE event typeがあれば `on_{event type}`
7. `on_unknown`

たとえば `on_image` と `on_media` を両方登録した場合、画像では `on_image` だけが呼ばれます。`on_image` がなければ `on_media`、それもなければ `on_message` へfallbackします。

ハンドラ内の例外はPollingループへ再送出されず、エラーログへ記録されます。失敗を監視したい場合はハンドラ内で明示的に記録してください。

## 正規化メッセージ

```python
@bot.event
def on_message(event):
    message = event.get("normalized") or bot.normalize_message_event(event)
    print(message.get("message_type"))
```

メッセージイベントでは次の共通フィールドを返します。

| フィールド | 内容 |
|---|---|
| `kind` | image / video / fileは `media`。それ以外は原則 `message_type` |
| `message_type` | `text`, `image`, `video`, `file`, `audio`, `sticker`, `link` など |
| `bot_id` | 対象Official Account ID |
| `chat_id` | 対象チャットID |
| `message_id` | メッセージID |
| `timestamp` | messageまたは内側payloadのtimestamp |
| `content_hash` | content preview取得用hash |
| `media_url` | image / video / fileのpreview URL。組み立てられない場合は `None` |
| `sticker_media_url` | `sticker_id` から組み立てたsticker画像URL |
| `expired` | LINE側の期限切れ状態 |
| `expired_at` | LINE側の期限情報 |
| `text` | テキストまたはlink本文 |
| `url` | link URL |
| `title` | link title |
| `sticker_id` | sticker ID |
| `package_id` | sticker package ID |
| `file_name` | 元ファイル名 |
| `extension` | ファイル名または種別から推定した拡張子 |
| `duration` | 音声などの長さ |
| `audio` | 元メッセージ内のaudio辞書。なければ `{}` |
| `raw` | LINE側の元message辞書 |

注意点:

- `on_media` の対象にはaudio、sticker、linkも含まれますが、`kind == "media"` になるのはimage、video、fileだけです。
- `media_url` が作られるのも現在はimage、video、fileだけです。
- メッセージとして解析できないイベントは `{"kind": "unknown", "raw_event": event}` です。
- 未知の `message_type` はその値が `kind` に入ることがあります。
- LINE側の生データを調べる必要がある場合は `raw`、イベント全体なら元の `event` を使用します。

## 種別ごとの処理

```python
@bot.event
def on_media(event):
    message = event["normalized"]
    message_type = message.get("message_type")

    if message_type in {"image", "video", "file", "audio", "sticker", "link"}:
        saved = bot.save_message_media(
            event,
            f"./outputs/{message.get('message_id', 'message')}",
        )
        print("saved:", saved)
```

保存形式は[メッセージとメディア](messages-and-media.md#受信メディアを保存する)を参照してください。

## バックグラウンド実行

```python
import time

from LINELib import LineBot

bot = LineBot(cookie_path="lineoa-storage.json")
thread = bot.listen(
    botid="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    block=False,
)

try:
    time.sleep(60)
finally:
    bot.stop()
    thread.join()
```

`block=False` はdaemon `threading.Thread` を返します。`block=True` は停止まで呼出元をブロックし、戻り値は `None` です。同じ `LineBot` でPollingが動作中にもう一度 `listen()` すると `RuntimeError` になります。

`stop()` は停止フラグを立て、別threadから呼ばれた場合は最大5秒joinします。ハンドラを実行しているlistener thread自身から呼んでも自己joinしません。

## 接続と再接続

1回の接続は次の順序です。

1. `streamingApiToken` を取得する
2. tokenレスポンスに `connectionId` があれば `streaming/state` へ `{"connectionId": ..., "idle": True}` を送る
3. tokenレスポンスのbase URL、version、`lastEventId` を使ってSSEへ接続する
4. eventを受信するたびに最後のevent IDを保持する
5. tokenの `expiredAt` があれば、有効期限の60秒前までに接続時間を短縮する
6. 正常終了または例外後、停止されていなければ `reconnect_interval` 待って接続し直す

`max_reconnects=None` は再接続回数を制限しません。数値を指定した場合、連続した接続例外が上限を超えるとPollingを停止します。正常な接続ループを終えると失敗回数は0へ戻ります。

`lastEventId` は同じ `LineBot` インスタンスの再接続で引き継がれます。プロセス終了後に永続保存はされません。

## Polling設定

```python
bot = LineBot(
    cookie_path="lineoa-storage.json",
    ping_secs=30,
    device_type="",
    client_type="PC",
    reconnect_interval=5,
    max_reconnects=None,
    max_stream_seconds=7200,
)
```

| 引数 | 既定値 | 内容 |
|---|---:|---|
| `ping_secs` | `60` | Streaming APIへ渡すping間隔 |
| `device_type` | `""` | Streaming APIのdevice type |
| `client_type` | `"PC"` | Streaming APIのclient type |
| `reconnect_interval` | `5` | 再接続前の待機秒数 |
| `max_reconnects` | `None` | 連続接続エラーの上限。`None` は無制限 |
| `max_stream_seconds` | `82800` | 1接続の最大秒数 |

不正値は `ListenConfig` の検証で `ValueError` になります。

## 低レベルSSE

`LINELib.get_streaming_api_token_and_listen_stream_events()` はtoken取得と1回のSSE接続をまとめ、最後のevent IDを返します。自動再接続は `LineBot` が担当します。

`ChatService.stream_events()` はtokenを受け取るgeneratorです。さらに下の `SSEParser.iter_events()` はSSEテキスト行から `SSEEvent` を組み立てます。通常のBot実装ではこれらを直接使う必要はありません。詳細は[低レベルAPI](low-level-api.md#sseeventとsseparser)を参照してください。
