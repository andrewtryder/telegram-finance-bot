## 2024-05-30 - Added in-memory API caching
**Learning:** Telegram bots using python-telegram-bot run event loops. Blocking calls (like `requests`) block the entire bot from responding to other users.
**Action:** Always prefer async clients (like `httpx.AsyncClient`) in async event handlers. Additionally, added an in-memory cache to skip redundant network calls.
