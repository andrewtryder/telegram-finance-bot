<!-- OpenGraph / Social Preview -->
<meta property="og:title" content="Telegram Financial Bot" />
<meta property="og:description" content="A Telegram bot for stock, crypto, and index quotes, plus watchlists, charts, and price alerts via yfinance." />
<meta property="og:image" content="https://raw.githubusercontent.com/andrewtryder/telegram-finance-bot/main/docs/screenshot.png" />
<meta property="og:type" content="website" />
<meta property="og:url" content="https://github.com/andrewtryder/telegram-finance-bot" />

# Telegram Financial Bot

[![CI/CD Pipeline](https://github.com/andrewtryder/telegram-finance-bot/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/andrewtryder/telegram-finance-bot/actions/workflows/ci-cd.yml)
[![License](https://img.shields.io/github/license/andrewtryder/telegram-finance-bot)](https://github.com/andrewtryder/telegram-finance-bot/blob/main/LICENSE)

A Telegram bot for stock, crypto, and index quotes via yfinance (Yahoo Finance), with personal watchlists, charts, and chat-owned price alerts. Runs on **Cloudflare Workers** (serverless Python, zero ongoing costs) or **Railway / Docker / local** (full Python runtime with polling or webhooks).

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

---

## Supported Deployment Configurations

The bot supports both serverless (Cloudflare Workers) and containerized/process (Railway, Docker, local) environments through orthogonal configuration variables:

| Config | Environment | `BOT_MODE` | `STORAGE_BACKEND` | `WATCHLIST_ENABLED` | `ALERTS_ENABLED` | Description |
|:---:|---|:---:|:---:|:---:|:---:|---|
| **A** | Cloudflare Workers | `webhook` | `none` | `false` | `false` | **Default / Free Tier:** Completely stateless, zero database required. |
| **B** | Cloudflare Workers | `webhook` | `d1` | `true` | `false` | Serverless with Cloudflare D1 for personal watchlists. |
| **C** | Cloudflare Workers | `webhook` | `d1` | `true` | `true` | Full serverless with D1 storage and 1-minute Cron Trigger for alerts. |
| **D** | Railway / Docker | `webhook` | `sqlite` | `true` | `true` | Production webhook with persistent volume (`/app/data`) and SQLite. |
| **E** | Railway / Docker | `polling` | `sqlite` | `true` | `true` | Production long polling with SQLite persistence (1 replica). |
| **F** | Local / Dev | `polling` | `none` | `false` | `false` | Rapid local testing without database files or public HTTPS URLs. |

Unsupported combinations (such as `STORAGE_BACKEND=d1` on Python or `STORAGE_BACKEND=sqlite` on Cloudflare Workers) fail fast at startup with actionable error messages.

---

## Quickstart: Local Development

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the bot token.
2. Clone the repository and copy the environment template:
   ```bash
   cp .env.example .env
   ```
3. Set `TELEGRAM_BOT_TOKEN` in `.env`.
4. Run locally with [uv](https://docs.astral.sh/uv/) and Python 3.12+:

   ```bash
   # Config F (Stateless polling)
   uv sync --locked --no-dev
   BOT_MODE=polling STORAGE_BACKEND=none WATCHLIST_ENABLED=false ALERTS_ENABLED=false \
     uv run --locked --no-dev python -m bot.main
   ```

   Or run with SQLite storage (Config E):
   ```bash
   uv run --locked --no-dev python -m bot.main
   ```

> [!WARNING]
> Use **exactly one poller** per bot token. Never run local polling simultaneously with production polling or while a Telegram webhook is active.

---

## Cloudflare Workers Deployment

Cloudflare Workers runs the bot as a pure Python Worker using Cloudflare's Python runtime (`python_workers`). It responds instantly to Telegram webhooks without requiring long-running server instances or container billing.

### 1. Prerequisites

- Node.js 22+ and `wrangler` (`npx wrangler --version`)
- A Cloudflare account

### 2. Configure Secrets

Set required secrets in Cloudflare:

```bash
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_WEBHOOK_SECRET
```

The webhook secret must contain 1–256 ASCII characters (`[A-Za-z0-9_-]`). Optionally set `ALLOWED_CHAT_IDS` and `ADMIN_USER_IDS` secrets as comma-separated integers.

For local Worker emulation, store these in `.dev.vars` (never committed to git) and run `npx wrangler dev`.

### 3. Deploy Stateless (Config A)

By default, `wrangler.jsonc` is configured for **Config A** (`BOT_MODE=webhook`, `STORAGE_BACKEND=none`, watchlists/alerts disabled).

Deploy to Cloudflare:

```bash
npx wrangler deploy
```

Note your worker URL: `https://<worker-name>.<subdomain>.workers.dev`.

### 4. Optional: Enable D1 Persistence & Alerts (Config B & C)

To enable watchlists and price alerts on Cloudflare:

1. **Create the D1 database:**
   ```bash
   npx wrangler d1 create telegram-finance-bot
   ```
   Copy the `database_id` from the output.

2. **Apply migrations:**
   ```bash
   npx wrangler d1 migrations apply telegram-finance-bot --remote
   ```

3. **Update `wrangler.jsonc`:**
   Add the D1 binding and enable feature flags:
   ```jsonc
   {
     "vars": {
       "BOT_MODE": "webhook",
       "STORAGE_BACKEND": "d1",
       "WATCHLIST_ENABLED": "true",
       "ALERTS_ENABLED": "true"
     },
     "d1_databases": [
       {
         "binding": "DB",
         "database_name": "telegram-finance-bot",
         "database_id": "<database-id-from-step-1>",
         "migrations_dir": "cloudflare/migrations"
       }
     ],
     "triggers": {
       "crons": ["* * * * *"]
     }
   }
   ```
   *(Omit `"triggers"` if `ALERTS_ENABLED="false"`.)*

4. **Redeploy:**
   ```bash
   npx wrangler deploy
   ```

---

## Webhook Management & Switching

Use the built-in management CLI (`bot.manage_webhook`) to register, inspect, or delete your Telegram webhook safely.

### Register a Webhook

Set environment variables in your shell or private `.env` and register:

```bash
export TELEGRAM_BOT_TOKEN="<bot-token>"
export TELEGRAM_WEBHOOK_SECRET="<webhook-secret>"
export WEBHOOK_URL="https://<worker-host>/webhook"

python -m bot.manage_webhook register
```

### Inspect Webhook Status

```bash
python -m bot.manage_webhook info
```

Displays registered URL, custom certificate status, pending update count, and recent delivery error messages.

### Remove Webhook (Switching to Polling)

Before starting a polling instance on Railway or locally, delete the webhook from Telegram:

```bash
python -m bot.manage_webhook remove
```

Telegram will reject polling (`getUpdates`) calls if a webhook is currently active.

---

## Railway & Docker Deployment

### Docker

Run with a persistent SQLite volume:

```bash
docker pull ghcr.io/andrewtryder/telegram-finance-bot:latest
docker run -d \
  --name telegram-finance-bot \
  -v bot-data:/app/data \
  --env-file .env \
  ghcr.io/andrewtryder/telegram-finance-bot:latest
```

### Deploy on Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/6k39OM?referralCode=cPw57c&utm_medium=integration&utm_source=template&utm_campaign=generic)

1. Deploy from this repository.
2. **For Polling (Config E):**
   - Ensure Telegram webhook is deleted (`python -m bot.manage_webhook remove`).
   - Set `BOT_MODE=polling`.
   - Set `STORAGE_BACKEND=sqlite`.
   - Mount a persistent volume at `/app/data`.
   - Keep replicas set to **1** (Telegram allows only one poller per bot token).
3. **For Webhooks (Config D):**
   - Set `BOT_MODE=webhook`.
   - Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_SECRET`.
   - Set `STORAGE_BACKEND=sqlite` with persistent volume `/app/data`.
   - Generate a Railway domain and register:
     `WEBHOOK_URL="https://<railway-domain>/webhook" python -m bot.manage_webhook register`

---

## Portability & Operational Notes

- **Database Separation:** Cloudflare D1 and Railway/Docker SQLite are separate storage engines. They do not automatically synchronize. Switching between Railway and Cloudflare starts with an independent database unless manually exported/imported.
- **Alert Semantics:** On Cloudflare, price alerts are evaluated once per minute by scheduled Cron Triggers using an atomic claim lease (`claimed_at`). If alert delivery succeeds in Telegram but a database acknowledgment times out, at-least-once delivery semantics apply.
- **Quote Engine:** The Python runtime uses `yfinance`; Cloudflare Workers query Yahoo Finance HTTPS endpoints directly in Python. Minor differences in formatting or rounding may occur. Charts in Cloudflare Workers are rendered using lightweight, pure-Python PNG generation without `matplotlib`.
- **Update Deduplication:** Telegram webhooks include built-in update deduplication via `processed_updates` (when D1 is bound) or an in-memory cache to prevent duplicate processing during Telegram retries.
- **Admin Stats:** In webhook environments, `/admin stats` counts represent the in-memory lifetime of the active worker instance.

---

## CI/CD & Rollback

- **Validation:** GitHub Actions automatically tests every push and pull request with `pytest`, `ruff check`, `ruff format`, and `wrangler deploy --dry-run`.
- **Manual Deployment:** Deployments are triggered manually via **GitHub Actions Workflow Dispatch** (`.github/workflows/ci-cd.yml`):
  - `none`: Validation only, no deployments.
  - `cloudflare`: Deploys only to Cloudflare Workers (requires `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`).
  - `railway`: Deploys only to Railway (requires `RAILWAY_API_TOKEN`).
- **Worker Rollback:** To instantly roll back Cloudflare Workers to a previous version without redeploying code:
  ```bash
  npx wrangler rollback
  ```
  If the webhook URL changed during rollback, re-register the endpoint using `python -m bot.manage_webhook register`.
