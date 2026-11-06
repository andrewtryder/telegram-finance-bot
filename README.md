<!-- OpenGraph / Social Preview -->
<meta property="og:title" content="Telegram Financial Bot" />
<meta property="og:description" content="A Telegram bot for stock, crypto, and index quotes, plus watchlists, charts, and price alerts via yfinance." />
<meta property="og:image" content="https://raw.githubusercontent.com/andrewtryder/telegram-finance-bot/main/docs/screenshot.png" />
<meta property="og:type" content="website" />
<meta property="og:url" content="https://github.com/andrewtryder/telegram-finance-bot" />

# Telegram Financial Bot

[![CI/CD Pipeline](https://github.com/andrewtryder/telegram-finance-bot/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/andrewtryder/telegram-finance-bot/actions/workflows/ci-cd.yml)
[![License](https://img.shields.io/github/license/andrewtryder/telegram-finance-bot)](https://github.com/andrewtryder/telegram-finance-bot/blob/main/LICENSE)

A Telegram bot for stock, crypto, and index quotes via yfinance (Yahoo Finance), with personal watchlists, charts, and chat-owned price alerts.

![Telegram Financial Bot in action](https://raw.githubusercontent.com/andrewtryder/telegram-finance-bot/main/docs/screenshot.png)

## Features

- `/stock` `/stockinfo` `/stocknews` `/marketcap` — quotes and company data
- `/crypto` `/indices` — crypto pairs and major market indices
- `/search` — find Yahoo Finance symbols
- `/compare` — side-by-side quotes (2–4 tickers)
- `/chart` — closing-price chart PNG
- `/watchlist` — personal list (max 10), shared across your chats
- `/alert` — one-shot price alerts (max 20 per chat); chat-owned — fire into the chat; anyone there can list or remove
- `/admin stats` — owner-only in-memory command/error counts (`ADMIN_USER_IDS`)

## Run

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. `cp .env.example .env` and set `TELEGRAM_BOT_TOKEN` (see [`.env.example`](.env.example) for optional vars).
3. Run with Docker (volume keeps watchlists/alerts):

```bash
docker pull ghcr.io/andrewtryder/telegram-finance-bot:latest
docker run -v bot-data:/app/data --env-file .env ghcr.io/andrewtryder/telegram-finance-bot:latest
```

Or locally with [uv](https://docs.astral.sh/uv/) and Python 3.12+:

```bash
uv sync --locked --no-dev
uv run --locked --no-dev python -m bot.main
```

Use one poller per bot token — don’t run local and production against the same token at once.
Polling refuses to start while Telegram has an active webhook. Remove the webhook
with Telegram's `deleteWebhook` API before switching back to polling.

Watchlists and alerts default to enabled. Set `WATCHLIST_ENABLED=false` or
`ALERTS_ENABLED=false` to disable either feature. With both disabled,
`STORAGE_BACKEND=none` avoids creating a database.

## Cloudflare webhook

The Worker handles updates directly without a container or an application
database. It uses Yahoo Finance's HTTP endpoints for stock and cryptocurrency
quotes, indices, comparison, symbol search, company information and news.
Yahoo may block or rate-limit
these requests; the bot reports unavailable data when that happens. Quote
details can differ from the Python/yfinance implementation. Webhook charts are
lightweight PNG line plots with price and date labels; their rendering differs
from matplotlib. Watchlists and alerts require an optional D1 database; the default
stateless configuration keeps them disabled. Webhook admin counts are per
Worker instance and reset when it restarts.

1. Install Node.js 22+ and Wrangler. Set Worker secrets with `wrangler secret put`:
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, and optionally
   `ALLOWED_CHAT_IDS` and `ADMIN_USER_IDS`. The webhook secret must contain
   1–256 ASCII letters, digits, underscores or hyphens.
2. Run `wrangler deploy`. The Worker is configured with `BOT_MODE=webhook`,
   `STORAGE_BACKEND=none`, and watchlists and alerts disabled.
3. Stop any running poller. Set `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_WEBHOOK_SECRET`, and `WEBHOOK_URL=https://<worker-host>/webhook`
   in your shell or a private environment file, then run
   `python -m bot.manage_webhook register`. Use the same secret as
   the Worker. Run the script with `info` to check or `remove` to unregister.

For local testing, put Worker secrets in an ignored `.dev.vars` file and run
`wrangler dev`. `GET /health` checks the HTTP handler. Webhook mode is
stateless: Telegram retries can result in duplicate replies, especially after
errors or restarts.

To enable persistent features, create a D1 database and bind it as `DB` with
`migrations_dir` set to `cloudflare/migrations`. Apply its migrations before
setting `STORAGE_BACKEND=d1` and enabling `WATCHLIST_ENABLED` or
`ALERTS_ENABLED`. When alerts are enabled, configure a Cron Trigger such as
`* * * * *`; leave it absent when alerts are disabled. Alert delivery uses a
short claim lease and may repeat if delivery succeeds but the confirmation
cannot be saved. On Railway, the Python webhook server uses the same handlers
as polling, supports `STORAGE_BACKEND=sqlite` and checks enabled alerts once
per minute; mount `/app/data` to preserve the database.

For example, after `wrangler d1 create telegram-finance-bot`, add the
returned database ID to `wrangler.jsonc`:

```json
{
  "d1_databases": [{
    "binding": "DB",
    "database_name": "telegram-finance-bot",
    "database_id": "<database-id>",
    "migrations_dir": "cloudflare/migrations"
  }],
  "triggers": { "crons": ["* * * * *"] }
}
```

Merge those properties into the existing configuration, and include
`triggers` only when alerts are enabled. Run
`wrangler d1 migrations apply telegram-finance-bot --remote`, update the
feature flags in `vars`, then deploy. D1 provisioning and migrations require
an API token with the corresponding D1 permissions. Existing SQLite data is
not automatically copied to D1.

## Deploy on Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/6k39OM?referralCode=cPw57c&utm_medium=integration&utm_source=template&utm_campaign=generic)

1. Deploy from this repo (or the button above).
2. For webhook mode, set `BOT_MODE=webhook`, the Telegram token, webhook
   secret and any allowlists. Use `STORAGE_BACKEND=none` with both optional
   features disabled, or `STORAGE_BACKEND=sqlite` with a volume. Register
   the Railway HTTPS URL after switching traffic away from Cloudflare.
3. For polling, remove the webhook, set `BOT_MODE=polling`, and mount a
   volume at `/app/data` for SQLite. Keep replicas at **1**.

GitHub Actions runs tests on pushes and pull requests. Deployments are manual:
use workflow dispatch and select exactly one target. Deploying a target does
not automatically switch Telegram; register its webhook only after confirming
the previous target is stopped. Roll back to a previous Worker-only version with
`wrangler rollback` and register the desired endpoint again if its URL changed.
The retired container version cannot be rolled back without rebuilding it.
