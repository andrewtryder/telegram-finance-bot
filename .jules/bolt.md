## 2024-05-30 - Added in-memory API caching
**Learning:** Telegram bots using python-telegram-bot run event loops. Blocking calls (like `requests`) block the entire bot from responding to other users.
**Action:** Always prefer async clients (like `httpx.AsyncClient`) in async event handlers. Additionally, added an in-memory cache to skip redundant network calls.
* When updating long multiline strings like 'get_help_text', splitting them by newline and using a list format (i.e. ' \n '.join(lines)) prevents syntax errors compared to manual replacements on concatenated strings.
