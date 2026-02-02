# LINELib

LINELibは、LINE公式アカウントのチャット・認証・自動化をPythonから簡単に扱えるライブラリです

## 特徴
- Seleniumによる認証・Cookie管理
- 複数Bot・チャットの取得・送信・監視
- 有料のメッセージ送信を使わずにメッセージを送信する
- ⬆️Push無限

## インストール
```
pip install lineoa
```

## 使い方
### 1. 初回認証（SeleniumによるCookie保存）
```python
from LINELib.linebot import LineBot
COOKIE_PATH = os.environ.get("LINEOA_COOKIE_PATH", "lineoa_cookie.json")
bot = LineBot(storage=COOKIE_PATH, ping_secs=20)  # 初回はSeleniumで手動ログイン
#storageを設定することによりcookieを保存
```

### 2. 以降はCookie自動復元
```python
from LINELib.linebot import LineBot
COOKIE_PATH = os.environ.get("LINEOA_COOKIE_PATH", "lineoa_cookie.json")
bot = LineBot(storage=COOKIE_PATH, ping_secs=20)
#次回からcookieを利用してログイン
```

### 3. Bot一覧・チャット一覧取得
```python
bots = bot.bots.ids  # {bot名: botId}
chats = bot.getChats(bot_id)  # ユーザーchatId一覧
```

### 4. メッセージ送信
```python
bot.sendMessage(bot_id, user_id, "こんにちは！")
```

### 5. 画像送信
```python
bot.sendFile(bot_id, chat_id, "sample.png")
```

### 6. メッセージ監視
```python
bot.listen(botid="U*****")
```

### 7. リプライ返信
```python
bot.sendMessage(bot_id=bot_id, chat_id=chat_id, text="りぷらい", quoteToken=quoteToken)
```

### 8. グループ内のメンバー全取得
```python
bot.getMembers(bot_id=bot_id, chat_id=chat_id)
```

### 9. 簡単なpolling例
```python
from LINELib.linebot import LineBot

bot = LineBot(
    cookie_path="lineoa-storage.json",  # cookieファイルパスのみ指定
    ping_secs=20
)

BOT_ID = "U****"

@bot.event
def on_message(event):
    payload = event.get('payload', {})
    chat_payload = payload.get('payload', {})
    message = chat_payload.get('message', {})
    text = message.get('text', '')
    if message.get('type') == 'text' and text == "ping":
        bot.sendMessage(bot_id=payload.get('botId'), chat_id=payload.get('chatId'), text="pong!")

if __name__ == "__main__":
    bot.listen(botid=BOT_ID)
```

## サンプル
`example` を参照してください。

## クラス構成
- `linebot` ... モダンな設計思想に基づくクラス
- `LINELib` ... 全機能統合のメインクラス
- `AuthService` ... 認証・Cookie管理
- `ChatService` ... チャットAPI
- `LINEOAError` ... 例外クラス

## 注意事項
自己責任での使用
20message /1m のレートリミットが存在

## ライセンス
MIT License








