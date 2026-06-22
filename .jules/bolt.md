## 2024-05-30 - Added in-memory API caching
**Learning:** Telegram bots using python-telegram-bot run event loops. Blocking calls (like `requests`) block the entire bot from responding to other users.
**Action:** Always prefer async clients (like `httpx.AsyncClient`) in async event handlers. Additionally, added an in-memory cache to skip redundant network calls.

## 2024-05-31 - Transitioned to yfinance for market data
**Learning:** `yfinance` is a synchronous library. Calling it directly in an async event handler blocks the event loop, causing the bot to become unresponsive.
**Action:** Used `asyncio.to_thread` to run `yfinance` calls in a separate thread, preserving the non-blocking nature of the Telegram bot's event loop.
