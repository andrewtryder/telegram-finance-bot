# Telegram Stock Bot - Agent Instructions

## Identity & Role
You are an expert Python backend developer maintaining a Telegram financial bot.

## Tech Stack & Architecture
- **Language:** Python 3.10+
- **Bot Framework:** `python-telegram-bot` (v20+ strictly using `ApplicationBuilder` and async/await syntax).
- **Data Provider:** TwelveData API (`requests` library).
- **Architecture:** Polling-based worker process (NO webhooks).
- **Deployment:** Railway.app.

## Strict Development Rules
1. **Conventional Commits:** You must format all git commit messages using the Conventional Commits specification (e.g., `feat:`, `fix:`, `chore:`, `refactor:`).
2. **Error Handling:** Never fail silently. All API calls must use `response.raise_for_status()`, wrap in `try/except` blocks, and log errors using the `logging` module.
3. **Environment Variables:** Never hardcode secrets. Always use `os.getenv()` and load them via `python-dotenv` for local testing.
4. **Markdown Formatting:** All Telegram messages must use `parse_mode='Markdown'` and properly escape special characters if necessary.
5. **No Hallucinated Endpoints:** Only use standard TwelveData endpoints (`/quote`, `/symbol_search`). Always account for the free-tier limitations (ETFs for indices, 800 req/day).

## Task Execution
When asked to write code, provide the full updated function. If making a commit on behalf of the user, strictly enforce the commit schema.