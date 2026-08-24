# LINELib ドキュメント

このドキュメントは、LINELib 7.7.14の実装を基準にしています。LINELibはLINEヤフー株式会社の公式SDKではなく、LINE Official Account Managerの内部APIを扱う非公式ライブラリです。APIのレスポンス形式や認証フローは予告なく変わる可能性があります。

## 最初に理解すること

LINELibには3段階の入口があります。

| 層 | 主なクラス | 適した用途 |
|---|---|---|
| 高レベル | `LineBot` | 通常の送受信、Polling、イベントハンドラ、メディア保存 |
| 中間レベル | `LINELib` | async送信、SSEの直接制御、補助オブジェクトの利用 |
| 低レベル | `ChatService`, `AuthService` | 認証済みSessionやXSRF tokenを自分で管理する高度な処理 |

初めて使う場合は `LineBot` から始めてください。クラスを混在させる必要はありません。

## 学習順

1. [はじめに](getting-started.md)
   インストール、必要なID、初回ログイン、送信、Pollingまでを一度動かします。
2. [認証](authentication.md)
   保存Cookie、直接HTTPログイン、Chrome/Edge対話ログイン、メールOTP、安全上の注意を説明します。
3. [メッセージとメディア](messages-and-media.md)
   テキスト、返信、ファイル、メンション、Flex、履歴取得、メディア保存を説明します。
4. [イベントとPolling](events-and-polling.md)
   SSEイベント、ハンドラ選択順、正規化フィールド、再接続と停止を説明します。
5. [LineBot API](linebot-api.md)
   `LineBot` のコンストラクタと全公開メソッドのリファレンスです。
6. [低レベルAPI](low-level-api.md)
   `LINELib`、`ChatService`、`AuthService`、`SSEEvent`、設定クラスを説明します。
7. [トラブルシューティング](troubleshooting.md)
   認証、OTP、ブラウザ、Cookie、403、Polling、レート制限などを症状別に確認できます。

## 用語

| 用語 | 意味 |
|---|---|
| `bot_id` | 操作するOfficial AccountのID。通常は `U` で始まります。 |
| `chat_id` | 送信先または受信元のチャットID。ユーザーまたはグループを指します。 |
| `at_id` | Official Accountの `basicSearchId`。Flex用カードの作成で使用します。 |
| `content_hash` | 画像・動画・ファイルのプレビュー取得に使う値です。 |
| `quoteToken` | 返信付きメッセージの送信に使う受信メッセージ由来の値です。 |
| XSRF token | `chat.line.biz` の変更系APIでCookieと一緒に必要になるトークンです。通常はライブラリが管理します。 |
| SSE | サーバーからイベントを連続受信する仕組みです。`LineBot.listen()` が接続と再接続を管理します。 |

## 動作モデル

`LineBot` を作成すると内部で `LINELib` が作成され、Cookieまたはログイン結果から `requests.Session` とXSRF tokenを準備します。`LineBot` は利用可能なBot一覧を先読みし、送信・取得・Pollingを同じSessionで実行します。

ほとんどの取得APIはLINE側のJSONを `dict` のまま返します。内部APIの生レスポンスであるため、すべてのキーがLINELibの安定仕様というわけではありません。一方、`normalize_message_event()` の戻り値は、受信形式の差を吸収するためにLINELibが定義した共通形式です。

## 対応範囲と非対応範囲

対応している主な機能:

- Official Account一覧、チャット一覧、履歴、メンバーの取得
- テキスト、返信、ファイル、メンション、カード型Flexの送信
- SSEイベントの受信、再接続、ハンドラへの振り分け
- 画像、動画、ファイル、ステッカー、linkメタデータの保存
- 管理画面関連情報の取得
- Cookie再利用、メールログイン、メールOTP、可視Chrome/Edgeログイン

このライブラリ単体では提供しないもの:

- Messaging APIのWebhook署名検証
- LINE LoginやMessaging APIの公式SDK互換性
- reCAPTCHAの解読・回避
- 内部API変更後の互換性保証
- Cookieや認証情報の暗号化保管

## セキュリティ

`lineoa-storage.json` にはログインCookieが平文で保存されます。このファイルをGitへ追加したり、ログへ出力したり、第三者へ渡したりしないでください。メールアドレス、パスワード、メールOTPもソースコードへ直接書かず、環境変数または対話入力を使用してください。

自分が管理権限を持つOfficial Accountだけで使用し、LINE側の利用条件と運用ルールを確認してください。

## 実行例

実行可能なサンプルは [`example/`](../example/) にあります。サンプルごとの目的と環境変数は[はじめに](getting-started.md#実行可能なexample)を参照してください。

## 実装を読む場合

- 高レベル: [`LINELib/linebot.py`](../LINELib/linebot.py)
- 中間レベル: [`LINELib/LINELib.py`](../LINELib/LINELib.py)
- 認証: [`LINELib/AuthService.py`](../LINELib/AuthService.py)
- HTTP API: [`LINELib/ChatService.py`](../LINELib/ChatService.py)
- SSEと正規化: [`LINELib/sse.py`](../LINELib/sse.py)
