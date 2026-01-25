# LINEOALib

LINEOALibは、LINE公式アカウントの管理・チャット・認証・自動化をPythonから簡単に扱えるライブラリです。

## 特徴
- Seleniumによる認証・Cookie管理
- 複数Bot・チャットの取得・送信・監視

## インストール
```
pip install -r requirements.txt
```

## 使い方
### 1. 初回認証（SeleniumによるCookie保存）
```python
from LINELib import LINELib
COOKIE_PATH = os.environ.get("LINEOA_COOKIE_PATH", "lineoa_cookie.json")
lib = LINELib(storage=COOKIE_PATH)  # 初回はSeleniumで手動ログイン
#storageを設定することによりcookieを保存
```

### 2. 以降はCookie自動復元
```python
COOKIE_PATH = os.environ.get("LINEOA_COOKIE_PATH", "lineoa_cookie.json")
lib = LINELib(storage=COOKIE_PATH)
#次回からcookieを利用してログイン
```

### 3. Bot一覧・チャット一覧取得
```python
bots = lib.bots.ids  # {bot名: botId}
chats = lib.chats.user.ids  # ユーザーchatId一覧
```

### 4. メッセージ送信
```python
lib.sendMessage(user_id, "こんにちは！", bot_id)
```

### 5. 画像送信
```python
lib.sendImage(chat_id, "sample.png", bot_id)
```

### 6. メッセージ監視
```python
lib.listen_messages(bot_id, chat_id, on_message=lambda msg: print(msg))
```

## サンプル
`example/api.py` を参照してください。

## クラス構成
- `LINELib` ... 全機能統合のメインクラス
- `AuthService` ... 認証・Cookie管理
- `ChatService` ... チャットAPI
- `LINEOAError` ... 例外クラス

## ライセンス
MIT License

