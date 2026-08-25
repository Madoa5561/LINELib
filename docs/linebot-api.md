# LineBot API

`LineBot` はLINELibの推奨入口です。認証Session、ローカルレート制限、Bot ID解決、SSE再接続、イベントハンドラを1つのオブジェクトで管理します。

## コンストラクタ

```python
from LINELib import LineBot

bot = LineBot(
    cookie_path="lineoa-storage.json",
    ping_secs=60,
    device_type="",
    client_type="PC",
    email=None,
    password=None,
    rate_limit=18,
    rate_limit_window=60,
    rate_limit_enabled=True,
    reconnect_interval=5,
    max_reconnects=None,
    max_stream_seconds=82800,
    get_2fa_code_callback=None,
    interactive_login=False,
    browser_channel="chrome",
    interactive_timeout=300,
)
```

| 引数 | 既定値 | 内容 |
|---|---|---|
| `cookie_path` | `"lineoa-storage.json"` | Cookieとローカル送信履歴のJSON保存先 |
| `ping_secs` | `60` | Streaming APIへ渡すping間隔 |
| `device_type` | `""` | Streaming APIのdevice type |
| `client_type` | `"PC"` | Streaming APIのclient type |
| `email` | `None` | LINEヤフーBusiness IDのメールアドレス |
| `password` | `None` | LINEヤフーBusiness IDのパスワード |
| `rate_limit` | `18` | ローカル送信上限回数 |
| `rate_limit_window` | `60` | 上限を数える秒数 |
| `rate_limit_enabled` | `True` | ローカル送信制限の有効／無効 |
| `reconnect_interval` | `5` | SSE再接続前の待機秒数 |
| `max_reconnects` | `None` | 連続接続エラー上限。`None` は無制限 |
| `max_stream_seconds` | `82800` | SSE 1接続の最大秒数 |
| `get_2fa_code_callback` | `None` | 6桁メールOTPを返す引数なし関数。`None` またはcallable |
| `interactive_login` | `False` | 可視ブラウザの公式ログイン画面を使うか。boolのみ |
| `browser_channel` | `"chrome"` | `chrome` または `msedge`。Cookie Sessionの認証用headerにも反映 |
| `interactive_timeout` | `300` | ブラウザ起動から公式ログイン画面での認証完了までの待機秒数。OTP callbackと後続HTTP確認は対象外。bool以外の有限の正数 |

`email` と `password` は必ず両方を渡してください。片方だけではメールログインが開始されません。保存Cookieが有効なら、認証情報を渡していてもCookieが先に使われます。

`ping_secs`、`reconnect_interval`、`max_reconnects`、`max_stream_seconds` は `ListenConfig` で検証され、不正値では `ValueError` です。認証の詳細は[認証](authentication.md)を参照してください。

## 戻り値と例外の共通規則

- 多くの取得APIはLINE内部APIのJSONを `dict` のまま返します。
- テキスト送信は成功時に通常 `{}` を返します。
- ファイル送信はLINE側の送信レスポンスを `dict` で返します。
- 送信がローカルレート制限に達した場合は例外ではなく `{"ratelimit": True, "ratelimit_after": UNIX timestamp}` を返します。
- HTTP失敗、不正レスポンス、認証失敗は原則 `LINEOAError` です。
- 必須の `chat_id`、`text`、`file_path` が `None` または空文字の高レベル送信は `ValueError` です。
- 管理情報取得に必要な `bot_id`、`chat_id`、国コードなどの欠落や、件数・真偽値の不正値はHTTP通信前に `LINEOAError` です。
- LINE内部API由来の辞書キーは変更される可能性があるため `.get()` で読み取ってください。

## 送信

| メソッド | 戻り値 | 内容 |
|---|---|---|
| `sendMessage(bot_id=None, chat_id=None, text=None, quoteToken=None)` | `dict` | テキストを送信。`quoteToken` で返信 |
| `sendFile(bot_id=None, chat_id=None, file_path=None)` | `dict` | ファイルをuploadして送信 |
| `create_and_send_flex(**kwargs)` | `int` | カード型メッセージを作成・送信し、card IDを返す |

`sendMessage()` と `sendFile()` は `bot_id=None` の場合にBot一覧の先頭を使います。複数Bot環境では明示してください。Flexの全引数は[カード型Flex](messages-and-media.md#カード型flex)を参照してください。

## レート制限

| メソッド | 戻り値 | 内容 |
|---|---|---|
| `getRateLimitStatus()` | `dict` | `limited`, `count`, `limit`, `window`, `enabled`, `ratelimit_after` を返す |
| `resetRateLimit()` | `None` | 保存JSON内のローカル送信時刻だけを空にする |

LINE側の制限とは別の、ライブラリ内の安全弁です。詳しくは[ローカルレート制限](messages-and-media.md#ローカルレート制限)を参照してください。

## Bot・チャット

| メソッド | 戻り値 | 内容 |
|---|---|---|
| `getBots()` | `BotsInfo` | 利用可能なOfficial Account一覧。`.ids` でID辞書 |
| `getChats(bot_id=None, limit=25)` | `dict` | チャット一覧。`limit` は1〜25。`bot_id` 省略時は最初のチャット対応Bot |
| `getChatMessages(bot_id=None, chat_id=None, limit=50, before=None, after=None)` | `dict` | 履歴取得。`chat_id` 必須 |
| `getMembers(bot_id=None, chat_id=None, limit=100)` | `dict` | グループチャットのメンバー取得。`chat_id` 必須 |

## 正規化・メディア

| メソッド | 戻り値 | 内容 |
|---|---|---|
| `normalize_message_event(event)` | `dict` | SSEイベントをLINELib共通メッセージ形式へ変換 |
| `save_message_media(event, file_path)` | `str` | content、sticker、link JSONを保存し、実パスを返す |
| `get_image_preview(bot_id, content_hash)` | `bytes` | content previewを取得 |
| `save_image_preview(bot_id, content_hash, file_path)` | `str` | content previewを保存 |
| `save_sticker_image(sticker_id, file_path)` | `str` | sticker画像を保存 |

正規化フィールドは[イベントとPolling](events-and-polling.md#正規化メッセージ)、保存規則は[受信メディアを保存する](messages-and-media.md#受信メディアを保存する)を参照してください。

`bot_id`、`content_hash`、`sticker_id` は空でない文字列、`file_path` は空でない文字列または `os.PathLike` が必要です。不正値はHTTP通信やファイル操作の前に `LINEOAError` になります。

## アカウント・管理情報

| メソッド | 戻り値 | 内容 |
|---|---|---|
| `get_me()` | `dict` | ログイン利用者情報 |
| `get_bot_account(bot_id, no_filter=True)` | `dict` | 指定Official Account情報。`no_filter` はbool |
| `get_csrf_token()` | `dict` | CSRF endpointのJSON |
| `get_whitelist_domains()` | `dict` | whitelist domain情報 |
| `get_me_settings_pc()` | `dict` | PC向け利用者設定 |
| `get_authorized_users(bot_id, biz_ids="__AUTO_RESPONSE")` | `dict` | 権限ユーザー情報 |
| `get_plugins(bot_id)` | `dict` | Botのplugin情報 |

## チャット状態・Bot設定

| メソッド | 戻り値 | 内容 |
|---|---|---|
| `get_pinned_messages(bot_id, chat_id)` | `dict` | ピン留めメッセージ |
| `set_typing(bot_id, chat_id)` | `dict` | 入力中状態を送信 |
| `get_chat_mode(bot_id)` | `dict` | チャットモード |
| `get_chat_mode_schedules(bot_id)` | `dict` | チャットモードschedule |
| `get_available_features(bot_id)` | `dict` | 利用可能feature |
| `get_banner_web(bot_id)` | `dict` | Web banner情報 |
| `get_call_session(bot_id)` | `dict` | call session情報 |
| `get_activities(bot_id, chat_id, limit=1)` | `dict` | チャットactivity。`limit` は1〜100 |
| `get_notes(bot_id, chat_id, limit=20, with_total=True)` | `dict` | note一覧。`limit` は1〜100、`with_total` はbool |
| `get_use_manual_chat(bot_id, chat_id)` | `dict` | 手動チャット利用状態 |

## 入力支援・共通情報

| メソッド | 戻り値 | 内容 |
|---|---|---|
| `get_recent_stickers(bot_id)` | `dict` | 最近使ったsticker |
| `get_recent_emojis(bot_id)` | `dict` | 最近使ったemoji |
| `get_saved_replies(bot_id, query="", exclude_username_placeholder=False, sort_key="CREATED_AT", page_size=25, page=1)` | `dict` | 保存済み返信を検索・ページ取得。`sort_key` は空でない文字列、`page_size` は1〜100、`page` は1以上、除外フラグはbool |
| `get_clock_now()` | `dict` | 管理APIの現在時刻情報 |
| `get_holiday(country="JP")` | `dict` | 国コードに対応する休日情報 |

## イベントとPolling

| メソッド | 戻り値 | 内容 |
|---|---|---|
| `event(func)` | 登録した関数 | 関数名をキーにハンドラ登録。decoratorとして使用 |
| `dispatch(event_type, event)` | `None` | 1イベントを正規化し、優先順位に従ってハンドラへ配送 |
| `listen(botid=None, block=True)` | `Thread` または `None` | SSE Polling開始。`botid` 省略時は最初のチャット対応Bot |
| `stop()` | `None` | Polling停止フラグを設定し、必要ならlistenerをjoin |
| `close()` | `None` | Pollingを停止し、保持している認証済みHTTP Sessionも閉じる |

`dispatch()` は通常 `listen()` から内部的に呼ばれます。テストや保存イベントの再生で手動配送する場合、`event` は少なくとも `payload` を持つ辞書にしてください。

イベント選択順とthread動作は[イベントとPolling](events-and-polling.md)を参照してください。

`stop()` 後は同じインスタンスでPollingやAPI操作を再開できます。インスタンスを今後使わない場合は、接続資源を確実に解放するため `close()` を呼んでください。

## 主な公開属性

| 属性 | 内容 |
|---|---|
| `cookie_path` | 使用中の保存JSONパス |
| `listen_config` | 検証済み `ListenConfig` |
| `ping_secs`, `device_type`, `client_type` | Polling設定の参照値 |
| `handlers` | `{ハンドラ名: 関数}` の登録辞書 |
| `running` | Polling loopの動作状態 |
| `reconnect_interval`, `max_reconnects` | 再接続設定 |

先頭が `_` の属性は内部実装です。特に `_session`、`_xsrf_token`、`_lib` への依存は将来の互換性が保証されません。高度な処理では[低レベルAPI](low-level-api.md)の公開クラスを直接作成してください。
