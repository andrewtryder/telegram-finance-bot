# Codex Agent Improvement Brief

This document is the implementation handoff for hardening and polishing `telegram-stock-price-bot` for public release.

The bot is a Python Telegram worker that provides stock, crypto, index, company-info, news, market-cap, and symbol-search commands. It uses `python-telegram-bot`, `yfinance`, `httpx`, `cachetools`, and Twelve Data for symbol search.

## Primary Goal

Prepare this repository for a safe, reliable, and polished public release.

The most important outcomes are:

1. Do not leak secrets in logs, cache keys, errors, CI output, or docs.
2. Make Telegram message formatting robust against malformed user input and provider-supplied text.
3. Add runtime resilience for network failures, provider latency, and unexpected handler exceptions.
4. Add real CI that runs tests and linting before deployment.
5. Improve packaging, dependency hygiene, and public-facing documentation.
6. Add a simple Railway deployment path, including a deploy button once a Railway template exists.

## Operating Instructions for the Agent

- Work in small, reviewable commits or pull requests.
- Prefer explicit tests for every behavior change.
- Do not introduce new paid services unless clearly optional.
- Do not log secrets or full provider URLs containing API keys.
- Do not run untrusted pull-request code under privileged GitHub Actions events.
- Keep the bot suitable for Railway worker deployment using `python -m bot.main`.
- Keep commands friendly for Telegram private chats and group chats.
- Preserve the existing command names unless a change is explicitly documented as breaking.

## Current Command Surface

The bot should support and document these commands:

- `/start` - Show welcome/help text.
- `/help` - Show welcome/help text.
- `/stock <ticker>` - Fetch a stock quote.
- `/crypto <symbol>` - Fetch a crypto quote.
- `/indices` - Fetch major market indices.
- `/stockinfo <ticker>` - Fetch detailed company info.
- `/stocknews <ticker>` - Fetch recent stock news.
- `/marketcap <ticker>` - Fetch market cap.
- `/search <query>` - Search symbols through Twelve Data.

The existing alias `/indicies` may remain for typo tolerance, but `/indices` should be the documented spelling.

## Priority 0: Safety and Secret Handling

### 0.1 Stop logging URLs that contain API keys

Problem:

- The Twelve Data API key is interpolated into the request URL.
- The shared fetch helper logs full URLs for cache hits and misses.
- This can leak `TWELVEDATA_API_KEY` into application logs.

Required changes:

- Stop passing API keys inside loggable URL strings.
- Use `httpx.AsyncClient.get(url, params=params)` or equivalent.
- Use a redacted or structured cache key that does not contain secrets.
- Log safe metadata only, such as provider name and query.
- Remove or downgrade raw provider response logging.

Acceptance criteria:

- No log line contains `TWELVEDATA_API_KEY` or a full URL with `apikey=`.
- Tests cover that search fetch/cache logging does not include secrets.
- Search still works when `TWELVEDATA_API_KEY` is configured.
- Search still returns a helpful message when `TWELVEDATA_API_KEY` is missing.

### 0.2 Review all secret surfaces

Required changes:

- Confirm `.env` remains ignored.
- Confirm `.env.example` contains placeholders only.
- Do not add secrets to README examples, tests, fixtures, screenshots, or workflow logs.
- Ensure GitHub Actions does not echo secret values.

Acceptance criteria:

- Secret-like values in docs/tests are obvious placeholders.
- CI commands do not print secret values.

## Priority 1: Telegram Message Formatting Hardening

### 1.1 Standardize parse mode and escaping

Problem:

- `/search` uses MarkdownV2 escaping, but other commands use Markdown with unescaped user/provider data.
- Provider-supplied values such as company names, summaries, news titles, and URLs can break Telegram formatting.
- User-supplied tickers and crypto symbols can also contain formatting characters.

Required changes:

Choose one project-wide approach:

Option A, preferred:

- Use Telegram HTML parse mode for rich messages.
- Escape all dynamic text with `html.escape()`.
- Render emphasis with safe HTML tags like `<b>...</b>`.

Option B:

- Use MarkdownV2 everywhere.
- Escape every dynamic segment with `telegram.helpers.escape_markdown(..., version=2)`.

Option C:

- Remove parse modes from provider-heavy replies.
- Use plain text for maximum robustness.

Acceptance criteria:

- Dynamic user input is escaped in `/stock`, `/crypto`, `/stockinfo`, `/stocknews`, `/marketcap`, `/indices`, and `/search`.
- Provider data is escaped before insertion into Telegram messages.
- Tests include malicious or formatting-heavy inputs such as `AAPL_*[]()`, company names with parentheses, and news titles containing Markdown characters.
- Telegram parse errors caused by malformed Markdown are no longer expected from normal provider data.

### 1.2 Validate Markdown or HTML links in stock news

Problem:

- News output renders provider-supplied titles and URLs as links.
- Bad or missing URLs can produce invalid Telegram markup.

Required changes:

- Validate URLs before rendering them as links.
- Only allow `http://` and `https://` links.
- If a URL is missing or invalid, show the escaped title as plain text.

Acceptance criteria:

- Tests cover valid URLs, missing URLs, and malformed URLs.
- News messages never create invalid Telegram markup.

## Priority 2: Input Validation and Abuse Resistance

### 2.1 Validate ticker, crypto, and search inputs

Problem:

- Current ticker/crypto normalization is permissive.
- Search accepts arbitrary length input.
- Public bots can be spammed or given malformed commands cheaply.

Required changes:

Implement centralized validation helpers, for example:

```python
STOCK_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-=^]{0,15}$")
CRYPTO_RE = re.compile(r"^[A-Z0-9]{1,15}([/-][A-Z0-9]{1,15})?$")
MAX_SEARCH_LEN = 64
```

Adjust exact rules as needed, but keep them documented and tested.

Acceptance criteria:

- Invalid stock symbols receive a helpful error message.
- Invalid crypto symbols receive a helpful error message.
- Overlong search queries receive a helpful error message.
- Valid examples still work: `AAPL`, `BRK.B`, `^GSPC`, `BTC`, `BTC/USD`, `ETH-USD`.

### 2.2 Add optional allowlist or rate limiting

Problem:

- The workflow references `ALLOWED_CHAT_IDS`, but the application currently does not appear to enforce it.
- A public Telegram bot should have basic abuse controls.

Required changes:

Pick and implement one clear mode:

Private mode:

- Support `ALLOWED_CHAT_IDS` as a comma-separated environment variable.
- Reject commands from unauthorized chats with a short, non-leaky message.

Public mode:

- Add per-user or per-chat throttling for provider-backed commands.
- Keep `/help` and `/start` permissive.

Hybrid mode, preferred:

- If `ALLOWED_CHAT_IDS` is set, enforce it.
- If it is not set, run publicly with lightweight rate limiting.

Acceptance criteria:

- Tests cover allowed and denied chats when `ALLOWED_CHAT_IDS` is set.
- Tests cover rate-limited provider commands if rate limiting is implemented.
- README documents the chosen behavior.

## Priority 3: Runtime Resilience

### 3.1 Add a global error handler

Problem:

- Individual handlers catch some exceptions, but there is no global `application.add_error_handler(...)` safety net.

Required changes:

- Add an async global error handler.
- Log unexpected exceptions with stack traces using `logger.exception`.
- Reply with a generic user-safe message when possible.
- Avoid exposing secrets, stack traces, or provider internals to Telegram users.

Acceptance criteria:

- Unhandled command exceptions are logged once with stack trace.
- Users receive a safe generic failure message when a reply is possible.
- Tests cover the global error handler.

### 3.2 Add explicit timeouts around yfinance calls

Problem:

- `httpx` calls have a timeout, but yfinance calls run in threads without an explicit outer timeout.

Required changes:

- Wrap `asyncio.to_thread(...)` provider calls in `asyncio.timeout(...)` or equivalent.
- Keep timeout values configurable or centralized.
- Return a helpful user-facing message on timeout.

Acceptance criteria:

- Tests cover yfinance timeout behavior.
- Slow provider calls do not hang command handling indefinitely.

### 3.3 Add small retry/backoff for transient provider failures

Required changes:

- Add retries for idempotent provider reads.
- Keep retry counts low, for example two attempts total or one retry.
- Use jittered backoff if practical.
- Do not retry validation failures or missing API-key failures.

Acceptance criteria:

- Tests cover one transient failure followed by success.
- Tests cover repeated provider failure returning a friendly error.

### 3.4 Reuse one HTTP client

Problem:

- The fetch helper creates a new `httpx.AsyncClient` per request.

Required changes:

- Create a shared async HTTP client at application startup or in a service object.
- Close it cleanly on shutdown.
- Configure default timeout and possibly user-agent.

Acceptance criteria:

- Tests do not rely on real network access.
- Client lifecycle is deterministic.
- Search still uses caching.

### 3.5 Polling startup behavior

Required changes:

- Consider `application.run_polling(drop_pending_updates=True)` for Railway/redeploy behavior.
- Document why this is enabled or why it is not enabled.

Acceptance criteria:

- Bot startup behavior is documented.

## Priority 4: CI/CD Hardening

### 4.1 Add real CI before deployment

Problem:

- The current workflow lints PR titles and deploys, but does not run tests, linting, formatting checks, or type checks before deployment.

Required changes:

Add a CI workflow that runs on `pull_request` and `push`:

- Checkout code.
- Set up Python.
- Install runtime and test dependencies.
- Run linting.
- Run tests.
- Optionally run type checking.

Recommended commands:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-test.txt
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/
```

Acceptance criteria:

- CI fails on test failures.
- CI fails on lint failures.
- CI runs before deployment on `main`.

### 4.2 Keep `pull_request_target` safe

Problem:

- `pull_request_target` runs with elevated repository context.
- It should not checkout or execute untrusted PR code.

Required changes:

- Keep semantic PR title linting under `pull_request_target` only if needed.
- Do not add checkout, tests, scripts, or dependency installation to `pull_request_target` jobs.
- Run code tests under normal `pull_request`.

Acceptance criteria:

- No untrusted PR code executes in `pull_request_target` jobs.

### 4.3 Separate deploy workflow from CI workflow

Required changes:

- Deploy only from trusted `main` pushes or manual dispatch.
- Make deployment depend on passing tests.
- Avoid hardcoded Railway service names.
- Move Railway service name into a GitHub repository variable or secret, for example `RAILWAY_SERVICE_NAME`.

Acceptance criteria:

- Railway deploy command uses a variable or secret for the service name.
- Deployment does not run on untrusted PRs.

## Priority 5: Dependency and Packaging Hygiene

### 5.1 Pin or constrain dependencies

Problem:

- Runtime dependencies are mostly unconstrained.

Required changes:

Choose one dependency strategy:

Option A:

- Keep `requirements.txt`, but constrain major versions.

Option B, preferred for maintainability:

- Add `requirements.in` and generate pinned `requirements.txt` with `pip-tools`.

Option C:

- Move to `pyproject.toml` with dependency groups.

Minimum acceptable constraints:

```txt
python-telegram-bot>=21,<22
python-dotenv>=1,<2
yfinance>=0.2,<0.3
httpx>=0.27,<1
cachetools>=5,<7
```

Acceptance criteria:

- Dependencies install cleanly in CI.
- Tests pass with the selected dependency strategy.
- README documents the install flow.

### 5.2 Add Dependabot

Required changes:

Add `.github/dependabot.yml` for:

- Python dependencies.
- GitHub Actions.

Example:

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

Acceptance criteria:

- Dependabot config is valid.

### 5.3 Add Ruff

Required changes:

- Add `ruff` to dev/test dependencies.
- Add `pyproject.toml` or `ruff.toml` with project lint/format rules.
- Fix lint violations.

Acceptance criteria:

- `ruff check .` passes.
- `ruff format --check .` passes.

## Priority 6: Documentation and Public Release Polish

### 6.1 Update README command coverage

Problem:

- README does not fully describe every implemented command.

Required changes:

- Document all current commands listed above.
- Include examples for each provider-backed command.
- Explain that `/search` requires `TWELVEDATA_API_KEY`.
- Explain that stock/crypto/index quotes use yfinance/Yahoo Finance data.

Acceptance criteria:

- README and bot help text agree on supported commands.

### 6.2 Add disclaimers

Required changes:

Add a concise disclaimer:

- Data may be delayed, unavailable, or inaccurate.
- This bot is for informational purposes only.
- It is not financial advice.

Acceptance criteria:

- README contains the disclaimer.
- Bot help text may include a short version if appropriate.

### 6.3 Add public project files

Required changes:

Add:

- `LICENSE`
- `SECURITY.md`
- `CONTRIBUTING.md`

Recommended content:

- License: MIT unless the maintainer chooses another license.
- Security: explain how to report vulnerabilities privately.
- Contributing: explain setup, tests, linting, branch/PR conventions, and no-secret policy.

Acceptance criteria:

- Files exist and are accurate for this project.

### 6.4 Add or update `.env.example`

Required changes:

Ensure `.env.example` documents all supported variables:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TWELVEDATA_API_KEY=your_twelvedata_api_key_here
ALLOWED_CHAT_IDS=
LOG_LEVEL=INFO
```

Only include variables that are actually implemented.

Acceptance criteria:

- `.env.example` matches implemented config behavior.

## Priority 7: Railway Deployment Button and Template

### 7.1 Add Railway-ready docs

The bot should remain deployable as a Railway worker with:

```bash
python -m bot.main
```

Required README deployment flow:

1. Create a Telegram bot with BotFather.
2. Copy the Telegram bot token.
3. Deploy the backend to Railway.
4. Add `TELEGRAM_BOT_TOKEN`.
5. Optionally add `TWELVEDATA_API_KEY` for `/search`.
6. Start the worker.

Acceptance criteria:

- README explains that Telegram does not host the code.
- README explains that Railway hosts the bot worker.

### 7.2 Add a Deploy on Railway button placeholder

Required changes:

- Add a Railway button once a Railway template has been created.
- Use a placeholder until the actual template URL exists.

Placeholder:

```md
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/template/YOUR_TEMPLATE_CODE)
```

Acceptance criteria:

- README clearly labels the button as a placeholder if no real template URL exists.
- Do not commit fake template codes as if they are real.

### 7.3 Railway template variables

When creating the Railway template, include:

Required:

- `TELEGRAM_BOT_TOKEN`

Optional:

- `TWELVEDATA_API_KEY`
- `ALLOWED_CHAT_IDS`, only if implemented
- `LOG_LEVEL`, only if implemented

Start command:

```bash
python -m bot.main
```

Acceptance criteria:

- The template deploys a worker, not a web server.
- The template does not require secrets at build time.

## Priority 8: Test Coverage Plan

Add or update tests for:

- Search with missing API key.
- Search with configured API key.
- Search does not log API keys.
- Fetch/cache helper does not log secret-bearing URLs.
- Markdown/HTML escaping for every command that renders dynamic text.
- Invalid stock symbols.
- Invalid crypto symbols.
- Overlong search queries.
- yfinance timeout.
- provider transient failure and retry.
- global error handler.
- allowlist behavior, if implemented.
- rate limiting behavior, if implemented.
- README/help command consistency, if practical.

## Suggested Implementation Order

1. Secret/logging cleanup.
2. Central Telegram formatting/escaping helper.
3. Input validation helper.
4. Global error handler.
5. Provider timeouts and retry behavior.
6. Optional allowlist/rate limiting.
7. CI with tests and Ruff.
8. Dependency constraints.
9. README updates.
10. LICENSE, SECURITY, CONTRIBUTING.
11. Railway deploy button/template docs.

## Definition of Done

The release-hardening work is complete when:

- No secrets can appear in normal logs.
- All dynamic Telegram output is escaped or rendered as plain text.
- Provider calls have bounded runtime.
- The bot has a global error handler.
- Tests cover validation, escaping, secret redaction, and provider failure paths.
- CI runs tests and linting before deploy.
- Deployment does not run on untrusted pull-request code.
- Dependencies are pinned or constrained.
- README accurately documents setup, commands, deployment, and disclaimers.
- Public project files exist: `LICENSE`, `SECURITY.md`, and `CONTRIBUTING.md`.
- Railway deployment instructions are clear, with a real button only after the template URL exists.

## Non-Goals for This Pass

Do not implement these unless explicitly requested:

- Paid market-data subscriptions.
- Portfolio tracking.
- Trading, brokerage integration, or order placement.
- User accounts or databases.
- Webhook deployment migration, unless replacing polling is a deliberate project decision.
- A Telegram manager bot for creating other bots.

## Notes for Future Enhancements

Potential follow-up features after public release:

- Inline query mode.
- Watchlists.
- Scheduled price alerts.
- More index mappings.
- Configurable quote currency for crypto.
- Dockerfile and docker-compose examples.
- Observability via structured JSON logs.
- Sentry or OpenTelemetry, if desired by the maintainer.
