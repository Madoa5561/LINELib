# LINELib

LINELib is an unofficial Python wrapper for LINE Official Account web chat operations.

It focuses on authenticated cookie reuse, chat/message APIs, file sending, message listening through SSE, and local safety controls such as internal rate limiting and reconnect handling.

> This library uses LINE web endpoints and Selenium-assisted login flows. Use it only for accounts and environments where you understand the operational and policy risks.

## Features

- Cookie-based session restore
- Selenium-assisted first login
- Bot account and chat list retrieval
- Text, mention, and file sending
- Local send rate limiter for sync and async sending
- SSE message/event listening
- Automatic listen reconnect with `lastEventId` tracking
- Safe `listen(block=False)` and `stop()` control
- Small structured helpers for listen/rate-limit/SSE behavior

## Installation

```bash
pip install lineoa
```

For local development:

```bash
pip install -e .
```

## Quick Start

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

bot.sendMessage(bot_id=BOT_ID, chat_id=CHAT_ID, text="hello")
```

On the first run, the library may open a Selenium-controlled browser to complete login and save cookies to `cookie_path`. Later runs reuse the saved cookie file.

## Rate Limiting

The library keeps a local send history in the storage file and blocks sends before they exceed the configured window.

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

When a send is blocked, send methods return a dictionary like:

```python
{
    "ratelimit": True,
    "ratelimit_after": 1710000000.0,
    "limit": 18,
    "window": 60.0,
}
```

The limiter is local safety logic. It does not guarantee that LINE will accept every request.

## Listening For Events

Register handlers with `@bot.event`.

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

`listen()` reconnects when the SSE stream ends or raises an exception. The last received event ID is remembered and passed back on reconnect.

### Non-blocking Listen

```python
thread = bot.listen(botid="Uxxxxxxxx", block=False)

# Do other work here.

bot.stop()
thread.join()
```

Use `stop()` to request shutdown. The listener uses a stop event internally and joins the worker thread for a short timeout.

## Sending Files

```python
bot.sendFile(
    bot_id="Uxxxxxxxx",
    chat_id="xxxxxxxx",
    file_path="sample.png",
)
```

## Async Sending

Async send helpers share the same local rate limiter.

```python
await bot._lib.async_send_message(
    user_id="xxxxxxxx",
    context="hello async",
    bot_id="Uxxxxxxxx",
)
```

## Main Classes

- `LineBot`: high-level bot facade for examples and user code
- `LINELib`: authenticated session wrapper and compatibility API
- `ChatService`: low-level LINE chat HTTP/SSE calls
- `AuthService`: Selenium/cookie login support
- `RateLimitConfig`: validates local rate-limit settings
- `ListenConfig`: validates listen/reconnect settings
- `SSEParser`: parses Server-Sent Events without network access
- `SSEEvent`: structured SSE event object

## Safety Notes

- Keep `lineoa-storage.json` private. It contains authentication cookies.
- Do not commit cookie files to source control.
- The rate limiter is intentionally conservative by default: `18` sends per `60` seconds.
- Callback errors are logged and isolated so one bad handler does not kill the listener.
- Network errors during listen are logged and retried according to `reconnect_interval` and `max_reconnects`.
- Actual LINE server limits and endpoint behavior may change.

## Testing

Run local tests:

```bash
python -m unittest discover -s tests
```

The included tests cover local rate-limit behavior and SSE parsing. They do not contact LINE.

## License

MIT License
