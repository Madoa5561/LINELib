# トラブルシューティング

まず例外の型、`LINEOAError.code`、`InteractiveLoginRequired.reason`、HTTP statusを確認してください。Cookieや認証情報そのものはログへ出さないでください。

## `interactive_login_required` / `reason="recaptcha"`

原因: ブラウザを使わない直接HTTPログインに対し、LINE側がreCAPTCHAを要求しました。

対応:

1. 対話ログイン用依存を入れる
2. `interactive_login=True` にする
3. Google Chromeなら `browser_channel="chrome"`、Edgeなら `"msedge"` にする
4. 開いた公式画面で、視覚的確認が出た場合だけ操作する

```powershell
python -m pip install "lineoa[interactive-login]"
```

LINELibはreCAPTCHAの解読・回避を行いません。

## OTPメールが届かない

- ログインレスポンスがメール認証画面まで進んだか確認する
- 迷惑メール、受信遅延、登録メールアドレスを確認する
- 古いOTPではなく最新の6桁コードを使う
- 同じログイン処理を何度も起動して複数コードを発行しない
- 低レベル利用時は、同じaccount SessionとXSRF tokenで `resend_email_otp()` を呼ぶ

OTPが不要なログインではcallback自体が呼ばれません。callback待ちが始まっていないだけなら異常ではありません。

## `Email verification code must contain exactly six digits.`

callbackの戻り値が6桁の数字ではありません。前後空白は除去されますが、全角数字、ハイフン、説明文を含めず、メールに届いた6桁だけを返してください。

## `Interactive login requires Playwright`

対話ログイン用の任意依存がありません。

```powershell
python -m pip install "lineoa[interactive-login]"
```

この実装はOSにインストール済みChrome/Edgeのchannelを使うため、通常は `playwright install chromium` は不要です。

## `Failed to launch the interactive browser channel`

- `browser_channel` が `chrome` または `msedge` か確認する
- 対応ブラウザがWindowsへインストール済みか確認する
- ブラウザの更新・インストールが途中でないか確認する
- サービスアカウントやGUIのない実行環境では、可視ブラウザを起動できるsessionで実行する

Chrome/Edge以外は意図的に拒否されます。

## ログイン画面が時間切れになる

`interactive_timeout` を増やします。

```python
from LINELib import LineBot

bot = LineBot(
    cookie_path="lineoa-storage.json",
    email="your-email@example.com",
    password="your-password",
    interactive_login=True,
    interactive_timeout=600,
)
```

値は0より大きい秒数にしてください。ブラウザ起動、ログイン画面内のネットワーク待機、reCAPTCHA操作、画面遷移を含む、公式ログイン画面での認証完了までの上限です。OTP callbackの入力待ちと、ブラウザ認証後のHTTP Session確認は含みません。

## Cookieファイルがない、空、壊れている

主なmessage:

- `cookie storage does not exist`
- `cookie storage is empty`
- `cookie storage is invalid`
- `Cookie storage load error`

初回ログインで新しい保存Cookieを作成してください。手作業でCookie JSONを修復するより、公式ログインをやり直す方が安全です。既存ファイルを調査する場合も、値をIssueやログへ貼らないでください。

Cookieだけで `LineBot` を作成した場合、Cookieの復元またはBot一覧取得に失敗すると `LINEOAError` で初期化を中止します。未認証Sessionのまま処理は続行しません。

## `No bot found` / `No bot_id found`

- Cookieが有効か `bot.getBots()` で確認する
- ログイン利用者に対象Official Accountの権限があるか確認する
- 複数Bot環境では `bot_id` を明示する
- 公式管理画面で対象アカウントが表示されるか確認する

`bot_id` は通常 `U` で始まるOfficial Account IDです。`@...` の `basicSearchId` とは異なります。

## 401 / 403 / CSRF関連エラー

- Cookieの期限切れ
- `XSRF-TOKEN` がない、または `chat.line.biz` のCookieと対応していない
- 低レベル `ChatService` に別Sessionのtokenを渡した
- LINE側で追加認証が必要になった
- endpointまたはclient仕様が変更された

高レベル `LineBot` で再ログインし直すと、SessionとXSRF tokenの組み合わせを揃えられます。`ChatService` を直接使う場合は、同じログイン結果から取得したSessionとtokenを渡してください。

## 404 / 不正レスポンス / JSON decode失敗

このライブラリは内部APIへ依存するため、LINE側のURL、method、payload、response schemaが変わった可能性があります。

1. 失敗したメソッドとstatusだけを記録する
2. 秘密情報を除外してresponseの構造を確認する
3. 同じ操作が公式管理画面で成功するか確認する
4. LINELibのversionと変更履歴を確認する
5. 再現テストを追加してendpoint実装を更新する

内部APIの生レスポンスを利用側で読むときは、固定indexより `.get()` を使って変更に備えてください。

## 送信されず `ratelimit` が返る

これはHTTPエラーではなく、LINELibのローカル制限です。

```python
result = bot.sendMessage(
    bot_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    chat_id="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    text="hello",
)

if result.get("ratelimit"):
    print(result["ratelimit_after"])
```

`ratelimit_after` は現在の実装では制限解除予定のUNIX timestampです。待機秒数が必要なら現在時刻との差を計算してください。`resetRateLimit()` はローカル履歴しか変更せず、LINE側の制限は解除しません。

## Pollingが接続と切断を繰り返す

- エラーログのHTTP statusとmessageを確認する
- Cookieが有効か `getBots()` で確認する
- `ping_secs >= 1` か確認する
- `max_stream_seconds > 0` か確認する
- tokenの `expiredAt` に合わせた正常な張り替えと、即時エラーを区別する
- 一時障害なら `reconnect_interval` を適切に増やす
- 調査中は `max_reconnects` を設定し、無限再接続を避ける

```python
from LINELib import LineBot

bot = LineBot(
    cookie_path="lineoa-storage.json",
    reconnect_interval=10,
    max_reconnects=5,
)
```

`max_reconnects=0` では最初の接続例外後に停止します。`None` は上限なしです。

## ハンドラが呼ばれない

- 関数名が `on_message`、`on_media`、`on_image` などの規則に合っているか
- decoratorが同じ `bot` instanceへ登録されているか
- より優先度の高い `on_{message_type}` が登録されていないか
- `bot.listen()` に正しい `botid` を渡しているか
- `on_unknown` で元eventを確認できるか

画像では `on_image` が `on_media` より優先されます。1つのイベントで両方は呼ばれません。詳しくは[ハンドラ名と選択順](events-and-polling.md#ハンドラ名と選択順)を参照してください。

## メディア保存に失敗する

- `normalized["content_hash"]` または `sticker_id` があるか
- `expired` / `expired_at` が期限切れを示していないか
- 出力先へ書込権限があるか
- linkは画像ではなくJSONとして保存される点を確認する
- `kind == "media"` だけで分岐するとaudio、sticker、linkが外れる点を確認する

すべての対象を保存する場合は `message_type` で判定してください。

## asyncでSession警告が出る

`LINELib` のasync wrapperが内部作成した `aiohttp.ClientSession` は自動で閉じます。`ChatService` のasyncメソッドへ自分のSessionを渡した場合は、呼出側で `async with` または `await session.close()` を行ってください。

## 不具合報告に含める情報

- LINELib version
- Python versionとOS
- 使用クラスとメソッド
- 例外型、status code、秘密値を除いたmessage
- 最小再現コード
- Cookie、メール、パスワード、OTP、token、完全なrequest headerを除外したresponse構造

CookieファイルやHARをそのまま公開Issueへ添付しないでください。
