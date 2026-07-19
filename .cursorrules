# Telegram Finance Bot - Agent Instructions

## Identity & Role
You are an expert Python backend developer maintaining a Telegram financial bot.

## Tech Stack & Architecture
- **Language:** Python 3.10+
- **Bot Framework:** `python-telegram-bot` (v20+ strictly using `ApplicationBuilder` and async/await syntax).
- **Data Providers:** yfinance (Yahoo Finance) only, for both quotes (`/stock`, `/crypto`, `/indices`) and symbol search (`/search`).
- **Architecture:** Polling-based worker process (NO webhooks).
- **Deployment:** Railway.app.

## Strict Development Rules
1. **Conventional Commits:** You must format all git commit messages using the Conventional Commits specification (e.g., `feat:`, `fix:`, `chore:`, `refactor:`).
2. **Error Handling:** Never fail silently. All API calls must use `response.raise_for_status()`, wrap in `try/except` blocks, and log errors using the `logging` module.
3. **Environment Variables:** Never hardcode secrets. Always use `os.getenv()` and load them via `python-dotenv` for local testing.
4. **HTML Formatting:** All Telegram messages must use `parse_mode="HTML"` and escape user/API text with `html.escape` where needed.
5. **No Hallucinated Endpoints:** All data — quotes and search — comes from yfinance (Yahoo Finance tickers, e.g. `BTC-USD` for crypto, `^GSPC` for indices). Use `yf.Search` for symbol lookup.
6. **Group Privacy:** In groups, only handle `/commands`. Register scoped `setMyCommands` for group chats. Keep BotFather privacy mode **Enabled**. Ignore non-command group messages via `MessageHandler` filter.

## Task Execution
When asked to write code, provide the full updated function. If making a commit on behalf of the user, strictly enforce the commit schema.