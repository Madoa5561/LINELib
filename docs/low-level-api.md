# 低レベルAPI

通常のBot実装では [`LineBot`](linebot-api.md) を使ってください。このページは、async処理、SSEの直接制御、認証済みSessionの持ち込み、内部APIの個別操作が必要な利用者向けです。

## 公開import

パッケージ直下から次をimportできます。

```python
from LINELib import (
    AuthService,
    ChatService,
    InteractiveLoginRequired,
    LINELib,
    LINEOAError,
    LineBot,
    ListenConfig,
    RateLimitConfig,
    SSEEvent,
    SSEParser,
    merge_dicts,
)
```

## レイヤー構成

```text
LineBot
  └─ LINELib
       ├─ AuthService
       ├─ ChatService
       └─ SSEEvent
```

- `LineBot`: event decoratorとSSE再接続を含む高レベルwrapper
- `LINELib`: 認証Sessionを保持してChatServiceへ渡す中間層
- `ChatService`: endpointごとのHTTP処理。SessionとXSRF tokenは呼出側が渡す
- `AuthService`: Cookie、メールログイン、OTP、対話ブラウザを管理
- `SSEEvent` / `SSEParser`: SSEテキストとメッセージ正規化

先頭が `_` の属性やメソッドは公開APIではありません。

## LINELib

### コンストラクタ

```python
from LINELib import LINELib

lib = LINELib(
    storage="lineoa-storage.json",
    email=None,
    password=None,
    rate_limit=18,
    rate_limit_window=60,
    rate_limit_enabled=True,
    get_2fa_code_callback=None,
    interactive_login=False,
    browser_channel="chrome",
    interactive_timeout=300,
)
```

`LineBot` と違い、Pollingの再接続設定は持ちません。`storage` は `LineBot.cookie_path` と同じ保存JSONです。認証引数の意味は[認証](authentication.md)、rate limitの意味は[メッセージとメディア](messages-and-media.md#ローカルレート制限)を参照してください。

`LINELib` は認証済みHTTP Sessionを保持します。利用終了時は、activeなSSE接続とSessionを確実に解放するため `close()` を呼んでください。

```python
lib = LINELib(storage="lineoa-storage.json")
try:
    bots = lib.get_bots()
finally:
    lib.close()
```

### 送信と履歴

| メソッド | 内容 |
|---|---|
| `send_message(user_id, context, bot_id=None, quoteToken=None)` | テキスト送信 |
| `send_file(chat_id, file_path, bot_id=None)` | ファイル送信 |
| `send_mention(bot_id, chat_id, mentionee_id)` | メンション送信 |
| `create_and_send_flex(bot_id, at_id, chat_id, title, image_url, tag_name="", tag_color="info", description="", action_label="", action_text="", delete_after_send=True)` | カード型メッセージ作成・送信 |
| `get_chat_messages(bot_id, chat_id, limit=50, before=None, after=None)` | 履歴取得 |
| `listen_messages(bot_id, chat_id, on_message=None)` | チャット単位のSSEを継続受信 |

送信先ID、Bot ID、メンション対象ID、テキスト本文、ファイルパスなどの必須値が `None` または空の場合は、通信やローカル送信枠の記録前に `LINEOAError` になります。

互換alias:

| alias | 呼び出すメソッド |
|---|---|
| `sendMessage(user_id, text, bot_id=None, quoteToken=None)` | `send_message()` |
| `sendFile(chat_id, file_path, bot_id=None)` | `send_file()` |
| `sendMention(bot_id, chat_id, mentionee_id)` | `send_mention()` |
| `getMessages(bot_id, chat_id, limit=50, before=None, after=None)` | `get_chat_messages()` |
| `getChats(bot_id, limit=25)` | `get_chats()` |
| `getMembers(bot_id, chat_id, limit=100)` | `get_chat_members()` |

新しいコードではsnake_caseを推奨します。`LINELib.sendMessage()` の第1引数は `user_id`、`LineBot.sendMessage()` の第1引数は `bot_id` なので、クラス間で位置引数を流用しないでください。

### async

| メソッド | 内容 |
|---|---|
| `async_send_message(user_id, context, bot_id=None, quoteToken=None)` | asyncテキスト送信 |
| `async_send_file(chat_id, file_path, bot_id=None)` | async upload・ファイル送信 |
| `async_send_mention(bot_id, chat_id, mentionee_id)` | asyncメンション送信 |
| `async_get_chat_messages(bot_id, chat_id, limit=50, before=None, after=None)` | async履歴取得 |

いずれも認証済みrequests Sessionから `chat.line.biz` にdomain/pathが適合するCookieだけを抽出し、`aiohttp` 側へ渡します。送信3種は同期APIと同じローカルレート制限を使います。

### Bot・チャット・管理API

| メソッド | 内容 |
|---|---|
| `get_bots()` | `BotsInfo` を返す |
| `get_chats(bot_id, limit)` | チャット一覧の生JSON |
| `get_chat_members(bot_id, chat_id, limit=100)` | メンバー一覧。`bot_id` と `chat_id` は必須 |
| `get_me()` | ログイン利用者 |
| `get_bot_account(bot_id, no_filter=True)` | Bot情報 |
| `get_csrf_token()` | CSRF endpointのJSON |
| `get_pinned_messages(bot_id, chat_id)` | ピン留めメッセージ |
| `set_typing(bot_id, chat_id)` | 入力中状態 |
| `streaming_state(bot_id, state)` | Streaming接続状態送信 |
| `get_whitelist_domains()` | whitelist domain |
| `get_me_settings_pc()` | PC設定 |
| `get_chat_mode(bot_id)` | チャットモード |
| `get_chat_mode_schedules(bot_id)` | チャットモードschedule |
| `get_available_features(bot_id)` | 利用可能feature |
| `get_banner_web(bot_id)` | Web banner |
| `get_call_session(bot_id)` | call session |
| `get_activities(bot_id, chat_id, limit=1)` | activity |
| `get_notes(bot_id, chat_id, limit=20, with_total=True)` | note |
| `get_authorized_users(bot_id, biz_ids="__AUTO_RESPONSE")` | 権限ユーザー |
| `get_use_manual_chat(bot_id, chat_id)` | 手動チャット状態 |
| `get_recent_stickers(bot_id)` | 最近のsticker |
| `get_recent_emojis(bot_id)` | 最近のemoji |
| `get_saved_replies(bot_id, query="", exclude_username_placeholder=False, sort_key="CREATED_AT", page_size=25, page=1)` | 保存済み返信 |
| `get_clock_now()` | 管理APIの時刻 |
| `get_holiday(country="JP")` | 休日情報 |
| `get_plugins(bot_id)` | plugin情報 |

### SSE

| メソッド | 内容 |
|---|---|
| `get_streaming_api_token_and_listen_stream_events(bot_id, device_type="", client_type="PC", ping_secs=60, last_event_id=None, on_event=None, stop_event=None, max_stream_seconds=82800)` | token取得、state送信、1回のSSE接続を実行し、最後のevent IDを返す |
| `listen_stream_events(streaming_api_token, device_type="", client_type="PC", ping_secs=60, last_event_id=None, on_event=None, max_stream_seconds=82800, base_url="https://chat-streaming-api.line.biz", version="v2")` | 取得済みtokenで1回のSSE接続 |

自動再接続loopが必要なら `LineBot.listen()` を使用してください。

`ping_secs` と `max_stream_seconds` は有限の正数である必要があります。SSEの接続中に発生した通信切断も `LINEOAError` として通知されます。

### メディア

| メソッド | 戻り値 | 内容 |
|---|---|---|
| `normalize_message_event(event)` | `dict` | 共通メッセージ形式 |
| `get_image_preview(bot_id, content_hash)` | `bytes` | content preview |
| `save_image_preview(bot_id, content_hash, file_path)` | `str` | previewを保存 |
| `save_sticker_image(sticker_id, file_path)` | `str` | stickerを保存 |
| `save_message_media(event, file_path)` | `str` | 種別に応じてcontent、sticker、link JSONを保存 |

### ローカル状態

| メソッド | 内容 |
|---|---|
| `get_final_send_time()` | 保存JSONの `FinalsendTime` を返す |
| `set_final_send_time(timestamp)` | `FinalsendTime` を保存 |
| `get_send_timestamps()` | window外を除去した `SendTimestamps` を返す |
| `add_send_timestamp(timestamp)` | 送信時刻を追加 |
| `check_rate_limit()` | 現在のローカル制限状態 |
| `reset_rate_limit()` | ローカル送信時刻を空にする |

これらは送信wrapperが内部的に使います。`ratelimit_after` は名前に反して「残り秒数」ではなく、現在の実装では制限解除予定のUNIX timestampです。

### propertyと補助オブジェクト

| property | 内容 |
|---|---|
| `bots` | 遅延取得した `BotsInfo`。結果をinstance内でcache |
| `chats` | 最初のチャット対応Botのチャットを遅延取得した `ChatsInfo`。結果をcache |
| `provider` | provider endpointの生JSON。結果をcache |

`BotsInfo.ids` は `{basicSearchIdまたはBot名: botId}` です。
省略時の送信先や `chats` propertyには、Bot一覧から `responseMode=BOT` を除いた最初のチャット対応Botを使用します。`BotsInfo.ids` 自体は確認用途のためBotモードを含む全一覧を保持します。

```python
lib = LINELib(storage="lineoa-storage.json")
print(lib.bots.ids)
print(lib.chats.group.ids)
print(lib.chats.user.ids)
```

`ChatsInfo.group` と `.user` は `ChatTypeIds` で、`.ids` がchat IDのlistです。各補助オブジェクトの `repr()` は名前とIDを読みやすく表示します。cacheを明示更新する公開メソッドはないため、同じinstanceでは初回取得結果が維持されます。

## ChatService

### コンストラクタと共通契約

```python
from LINELib import ChatService

chat = ChatService(request_timeout=30, upload_timeout=120, browser_headers=None)
```

`request_timeout` は通常HTTP、`upload_timeout` はファイルuploadの秒数で、どちらも有限の正数が必要です。`browser_headers` は省略時にWindows版Chromeのprofileを使い、`LINELib` からは選択したChrome / Edge profileが自動で渡されます。

ほとんどの同期メソッドは末尾に `session=None, xsrf_token=None` を受け取ります。変更・認証が必要なendpointでは、ログイン済み `requests.Session` と `chat.line.biz` のXSRF tokenを同じSessionから渡してください。省略時は未認証のmodule-level `requests` が使われる場合があり、通常の管理API操作には向きません。

asyncメソッドは `cookies`, `xsrf_token`, `aiohttp.ClientSession` を受け取ります。`cookies` は名前と値の辞書、またはdomain/pathを確認済みのCookie header文字列です。`session=None` なら内部で作成し、終了時に閉じます。外から渡したSessionは呼出側が閉じてください。

### 送信・メッセージ

| メソッド | 内容 |
|---|---|
| `send_message(bot_id, chat_id, message, ...)` | 任意の内部message辞書を送信。成功時 `{}` |
| `async_send_message(bot_id, chat_id, message, ...)` | async版 |
| `send_file(bot_id, chat_id, file_path, ...)` | upload後にファイル送信 |
| `async_send_file(bot_id, chat_id, file_path, ...)` | async版 |
| `send_mention(bot_id, chat_id, mentionee_id, ...)` | mention payloadを作って送信 |
| `get_chat_messages(bot_id, chat_id, ..., limit=50, before=None, after=None)` | 履歴 |
| `async_get_chat_messages(bot_id, chat_id, ..., limit=50, before=None, after=None)` | async履歴 |
| `listen_messages(bot_id, chat_id, on_message=None, ...)` | チャット単位のSSEを継続受信 |
| `mark_as_read(bot_id, chat_id, message_id, timestamp=None, ...)` | 指定メッセージまで既読 |

`listen_messages()` には停止callbackがないため、通常の受信には停止・再接続を管理できる `LineBot.listen()` を使用してください。
SSE読取中の通信切断は `LINEOAError` として通知されます。

### Bot・チャット

| メソッド | 内容 |
|---|---|
| `get_bot_accounts(..., limit=1000, no_filter=True)` | Bot一覧 |
| `get_bot_account(bot_id, no_filter=True, ...)` | Bot情報 |
| `get_chats(bot_id, ..., folder_type="ALL", tag_ids="", auto_tag_ids="", limit=25, prioritize_pinned_chat=True)` | 条件付きチャット一覧 |
| `get_chat(bot_id, chat_id, ...)` | 1チャット |
| `get_chat_members(bot_id, chat_id, limit=100, ...)` | メンバー |
| `async_get_chat_members(bot_id, chat_id, limit=100, ...)` | asyncメンバー |
| `get_pinned_messages(bot_id, chat_id, ...)` | ピン留め |
| `get_activities(bot_id, chat_id, limit=1, ...)` | activity |
| `get_notes(bot_id, chat_id, limit=20, with_total=True, ...)` | note |
| `get_use_manual_chat(bot_id, chat_id, ...)` | 手動チャット状態 |

### 設定・利用者・管理情報

| メソッド | 内容 |
|---|---|
| `get_me(...)` | ログイン利用者 |
| `get_csrf_token(session=None)` | CSRF endpoint |
| `get_whitelist_domains(...)` | whitelist domain |
| `get_me_settings_pc(...)` | PC設定 |
| `get_chat_mode(bot_id, ...)` | チャットモード |
| `get_chat_mode_schedules(bot_id, ...)` | schedule |
| `get_available_features(bot_id, ...)` | feature |
| `get_banner_web(bot_id, ...)` | banner |
| `get_call_session(bot_id, ...)` | call session |
| `get_authorized_users(bot_id, biz_ids="__AUTO_RESPONSE", ...)` | 権限ユーザー |
| `get_recent_stickers(bot_id, ...)` | 最近のsticker |
| `get_recent_emojis(bot_id, ...)` | 最近のemoji |
| `get_saved_replies(bot_id, query="", exclude_username_placeholder=False, sort_key="CREATED_AT", page_size=25, page=1, ...)` | 保存済み返信 |
| `get_clock_now(...)` | 管理APIの時刻 |
| `get_holiday(country="JP", ...)` | 休日 |
| `get_plugins(bot_id, ...)` | plugin |

### contentとSSE

| メソッド | 内容 |
|---|---|
| `get_content_preview(bot_id, content_hash, ...)` | preview bytes |
| `save_content_preview(bot_id, content_hash, file_path, ...)` | preview保存 |
| `get_sticker_image(sticker_id, session=None)` | sticker bytes |
| `save_sticker_image(sticker_id, file_path, session=None)` | sticker保存 |
| `get_streaming_api_token(bot_id, ...)` | Streaming token、URL、version、有効期限など |
| `streaming_state(bot_id, state, ...)` | 接続状態送信 |
| `stream_events(streaming_api_token, device_type="", client_type="PC", ping_secs=60, last_event_id=None, ..., max_stream_seconds=82800, base_url="https://chat-streaming-api.line.biz", version="v2")` | event辞書をyieldするgenerator |
| `set_typing(bot_id, chat_id, ...)` | 入力中状態送信 |

### カード型Flex

| メソッド | 内容 |
|---|---|
| `create_card_type_message(at_id, title, image_url, tag_name="", tag_color="info", description="", action_label="", action_text="", ...)` | Manager APIでcardを作成し、IDを返す |
| `send_flex_message(bot_id, chat_id, card_type_message_id, ...)` | card IDをchatへ送信 |
| `get_flex_json(bot_id, chat_id, message_id, timestamp=None, ...)` | 送信済みcardのFlex JSON取得 |
| `delete_card_type_message(at_id, card_id, ...)` | Manager APIのcardを削除 |
| `create_and_send_flex(bot_id, at_id, chat_id, title, image_url, ..., delete_after_send=True, ...)` | 作成・送信・任意削除をまとめて実行 |

## AuthService

### コンストラクタ

```python
from LINELib import AuthService

auth = AuthService(
    channel_id=None,
    channel_secret=None,
    access_token=None,
    cookie_store_path="lineoa-storage.json",
    request_timeout=30,
)
```

`cookie_store_path` はログインCookieのJSON保存先、`request_timeout` は認証HTTPの秒数で、有限の正数が必要です。`interactive_timeout` も同じ制約です。`channel_id` / `channel_secret` / `access_token` は別系統のtoken設定用で、Official Account ManagerのCookieログインとは別物です。

### 公開メソッド

| メソッド | 内容 |
|---|---|
| `login_with_email_and_2fa(email, password, get_2fa_code_callback, recaptcha_response="", stay_logged_in=True, xsrf_token=None, cookies=None, interactive_login=False, browser_channel="chrome", interactive_timeout=300)` | 保存Cookie、直接HTTP、対話ブラウザ、OTPを統合。`session`, `user_info`, `bot_ids` を返す |
| `login_with_email(email, password, recaptcha_response="", stay_logged_in=True, xsrf_token=None, cookies=None, session=None, referer=None)` | メールlogin endpointを1回呼ぶ低レベル処理。redirect・OTP・Cookie保存は行わない |
| `verify_email_otp(session, code, xsrf_token, referer=...)` | 同じaccount Sessionで6桁OTPを検証 |
| `resend_email_otp(session, xsrf_token, referer=...)` | 同じaccount SessionでOTP再送を要求 |
| `login_and_get_token(email, password, client_id, code_challenge, redirect_uri, state, session=None)` | PKCE OAuth flowを進め、authorization codeを返す |
| `get_access_token()` | コンストラクタへ設定済みのaccess tokenを返す。取得や更新はしない |
| `get_uid_map_from_at_ids(at_id_list, chat_service, session=None, xsrf_token=None)` | 認証済みBot一覧から `{at_id: bot_id}` を組み立てる |

`login_and_get_token()` は名前に `token` を含みますが、実際の戻り値はaccess tokenではなくOAuth authorization codeです。また、reCAPTCHAや追加認証があるflowを回避しません。

`login_with_email()` と `login_and_get_token()` は `session=None` の場合に内部作成したSessionを処理後に自動で閉じます。明示的に渡したSessionは呼出側で管理してください。`login_with_email_and_2fa()` が成功時に返す `result["session"]` は後続の認証済み通信で使うSessionなので、`AuthService` を直接利用する場合は不要になった時点で `close()` してください。

対話ブラウザの起動後にPlaywrightの通信・操作エラーが発生した場合も `LINEOAError` として通知されます。

認証全体の説明は[認証](authentication.md)を参照してください。

## SSEEventとSSEParser

### SSEEvent

```python
from LINELib import SSEEvent

sse_event = SSEEvent(
    id="event-id",
    event="message",
    data='{"payload": {}}',
)
```

| 属性・メソッド | 内容 |
|---|---|
| `id` | SSE id |
| `event` | SSE event名 |
| `data` | SSE dataの元文字列 |
| `payload` | `data` をJSON decode。失敗時は元文字列 |
| `as_dict()` | `{"id", "event", "data"}`。parsed payloadではなく元dataを含む |
| `message_payload()` | 内側のmessage辞書。なければ `None` |
| `normalized_message()` | 共通メッセージ辞書。なければ `None` |
| `image_url()` | 正規化後の `media_url`。なければ `None` |

### SSEParser

```python
from LINELib import SSEParser

lines = [
    "id: 1\n",
    "event: message\n",
    "data: {\"payload\": {}}\n",
    "\n",
]
events = list(SSEParser.iter_events(lines))
```

`iter_events(lines)` は `str` またはUTF-8の `bytes` 行を受け取り、SSEの複数data行を改行で連結して空行で `SSEEvent` を確定します。`:` で始まるkeepalive commentは無視します。fieldのコロン直後にある空白は1文字だけ除去し、末尾の空白は保持します。`id` fieldを省略したeventは直前のIDを引き継ぎ、値が空の `id` fieldはIDをリセットします。終端空行がない未完了eventはyieldせず破棄します。

## 設定クラス

### ListenConfig

```python
from LINELib import ListenConfig

config = ListenConfig(
    ping_secs=60,
    device_type="",
    client_type="PC",
    reconnect_interval=5,
    max_reconnects=None,
    max_stream_seconds=82800,
)
```

frozen dataclassです。`ping_secs >= 1`、`reconnect_interval >= 0`、`max_reconnects` は `None` または0以上、`max_stream_seconds > 0` を検証します。`LineBot` は個別引数から内部的に作成します。

### RateLimitConfig

```python
from LINELib import RateLimitConfig

config = RateLimitConfig(limit=18, window=60, enabled=True)
```

frozen dataclassで、`limit >= 1`、`window > 0`、`enabled` がboolであることを検証し、数値を `int` / `float` へ正規化します。現在の `LineBot` / `LINELib` コンストラクタがこのobjectを直接受け取るわけではなく、`rate_limit`, `rate_limit_window`, `rate_limit_enabled` の個別引数を使います。

## 例外

`LINEOAError(message, code=None, details=None)` は共通例外で、`.code` と `.details` を保持します。例外生成だけではログを出さないため、必要に応じてアプリ側の例外境界で記録してください。

`InteractiveLoginRequired(reason)` はそのサブクラスで、`.reason` と `code == "interactive_login_required"` を持ちます。捕捉順はサブクラスを先にします。

```python
from LINELib import InteractiveLoginRequired, LINEOAError

try:
    pass
except InteractiveLoginRequired as error:
    print(error.reason)
except LINEOAError as error:
    print(error.code, error.details)
```

## merge_dicts

```python
from LINELib import merge_dicts

result = merge_dicts({"a": 1}, {"a": 2, "b": 3})
assert result == {"a": 2, "b": 3}
```

第1辞書をcopyし、第2辞書で上書きした新しい辞書を返します。入力辞書は変更しません。
