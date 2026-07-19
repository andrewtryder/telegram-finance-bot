<!-- OpenGraph / Social Preview -->
<meta property="og:title" content="Telegram Financial Bot" />
<meta property="og:description" content="A Telegram bot for stock, crypto, and index quotes, plus watchlists, charts, and price alerts via yfinance." />
<meta property="og:image" content="https://raw.githubusercontent.com/andrewtryder/telegram-stock-price-bot/main/docs/screenshot.png" />
<meta property="og:type" content="website" />
<meta property="og:url" content="https://github.com/andrewtryder/telegram-stock-price-bot" />

# Telegram Financial Bot

[![CI/CD Pipeline](https://github.com/andrewtryder/telegram-stock-price-bot/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/andrewtryder/telegram-stock-price-bot/actions/workflows/ci-cd.yml)
[![Release Please](https://github.com/andrewtryder/telegram-stock-price-bot/actions/workflows/release-please.yml/badge.svg)](https://github.com/andrewtryder/telegram-stock-price-bot/actions/workflows/release-please.yml)
[![Docker Image Publish](https://github.com/andrewtryder/telegram-stock-price-bot/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/andrewtryder/telegram-stock-price-bot/actions/workflows/docker-publish.yml)
[![Docker Registry](https://img.shields.io/badge/docker-GHCR-blue?style=flat&logo=docker&logoColor=white)](https://github.com/andrewtryder/telegram-stock-price-bot/pkgs/container/telegram-stock-price-bot)
[![License](https://img.shields.io/github/license/andrewtryder/telegram-stock-price-bot)](https://github.com/andrewtryder/telegram-stock-price-bot/blob/main/LICENSE)

A Telegram bot for stock, crypto, and index quotes via yfinance (Yahoo Finance), with symbol search powered by the same source — every result is a symbol you can paste straight into `/stock`, `/crypto`, `/chart`, or `/watchlist`. Optional Honeybadger error reporting is supported.

## Preview

![Telegram Financial Bot in action](https://raw.githubusercontent.com/andrewtryder/telegram-stock-price-bot/main/docs/screenshot.png)

## Features

- `/start` / `/help` - Welcome message and command list (`/help stock` for command-specific help).
- `/stock <ticker>` - Fetches the current price of a stock (e.g., `/stock AAPL`), including pre/post-market when available.
- `/stockinfo <ticker>` - Fetches company information such as sector, industry, P/E ratio, dividend yield, and 52-week range (e.g., `/stockinfo AAPL`).
- `/stocknews <ticker>` - Fetches recent news headlines for a stock (e.g., `/stocknews AAPL`).
- `/marketcap <ticker>` - Fetches a company's market capitalization (e.g., `/marketcap AAPL`).
- `/compare <t1> <t2> [t3] [t4]` - Compares 2–4 stock quotes side by side.
- `/watchlist` / `/watchlist add|remove <ticker>` - Personal watchlist with compact quotes (max 10 per user), shared across private chats, groups, and channels.
- `/chart <ticker> [1mo|3mo|6mo|1y]` - Renders a closing-price line chart PNG.
- `/alert add <ticker> above|below <price>` - Create a one-shot price alert; `/alert list` and `/alert remove <id>` manage alerts (checked every 60s).
- `/crypto <symbol>` - Fetches the current price of a cryptocurrency (e.g., `/crypto BTC` or `/crypto ETH`).
- `/indices` - Fetches current levels of major market indices (S&P 500, Dow Jones, Nasdaq Composite).
- `/search <query>` - Search for a symbol via Yahoo Finance (e.g., `/search Apple`).

On startup, the bot removes any registered command menu button (`deleteMyCommands`) across private chats and groups so no menu bar appears in chats or channels.

**Requires Python 3.12+.**

## Group Chats

This bot is designed for command-only use in groups:

- **No menu bar:** On startup the bot clears any registered `/` menu bar commands via `deleteMyCommands` across all scopes.
- **Privacy mode (recommended):** In [@BotFather](https://t.me/BotFather), send `/setprivacy`, select your bot, and choose **Enable**. The bot will only receive messages that start with `/`, @mention the bot, or reply to the bot. This is enabled by default for new bots.
- **No reply keyboard:** `/start` and `/help` do not show a reply keyboard in private chats, groups, or channels.
- **Code-level filter:** Non-command messages in groups are ignored as a fallback if privacy mode is disabled in BotFather.

## Prerequisites

To run this bot locally or in production, you will need:

1. **Telegram Bot Token**:
   - Go to Telegram and search for the `@BotFather` bot.
   - Send `/newbot` and follow the instructions to create a new bot.
   - Copy the API token provided at the end.

2. **Allowed Chat IDs** (optional):
   - Set `ALLOWED_CHAT_IDS` to a comma-separated list of allowed Telegram user or group IDs (e.g., `12345678,-10012345678`) to restrict bot access.
   - If not set, or if set to `0` (used to explicitly allow public access), anyone can talk with the bot.

3. **Honeybadger API Key** (optional):
   - Set `HONEYBADGER_API_KEY` to enable error reporting. Optionally set `HONEYBADGER_ENVIRONMENT` (defaults to `RAILWAY_ENVIRONMENT` or `development`).

4. **Persistent data directory** (for `/watchlist` and `/alert`):
   - Set `DATA_DIR` to a writable path for the SQLite database (default `./data` locally, `/app/data` in Docker).
   - In production, mount a volume on that path so data survives redeploys.

See [`.env.example`](.env.example) for the full list of environment variables, including optional `LOG_FORMAT` (`json` or `text`; defaults to JSON when `RAILWAY_ENVIRONMENT` is set).

## Docker

The easiest way to run the bot. Pre-built Docker images (`linux/amd64`) are published automatically to the GitHub Container Registry.

- Pushes to `main` publish `latest` and traceable SHA tags.
- Release Please releases publish semantic version tags such as `0.3.0`, `0.3`, and `0`.

### Pull and run from GHCR

```bash
# Pull the latest image
docker pull ghcr.io/andrewtryder/telegram-stock-price-bot:latest

# Or pin a released version
docker pull ghcr.io/andrewtryder/telegram-stock-price-bot:0.3.0

# Run with env file and a volume for SQLite (watchlists/alerts)
docker run -v bot-data:/app/data --env-file .env ghcr.io/andrewtryder/telegram-stock-price-bot:latest
```

> **Note:** If the package is private, you must first authenticate: `echo $CR_PAT | docker login ghcr.io -u USERNAME --password-stdin`

### Run with Docker Compose

Create a `docker-compose.yml`:

```yaml
services:
  bot:
    image: ghcr.io/andrewtryder/telegram-stock-price-bot:latest
    restart: unless-stopped
    env_file:
      - .env
    environment:
      DATA_DIR: /app/data
    volumes:
      - bot-data:/app/data

volumes:
  bot-data:
```

Then:

```bash
docker compose up -d
```

### Build locally from source

```bash
docker build -t telegram-stock-price-bot .
docker run -v bot-data:/app/data --env-file .env telegram-stock-price-bot
```

## Local Setup

1. Clone this repository.
2. Create a virtual environment with **Python 3.12+** and activate it:
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the example environment file and fill in your keys:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and replace the placeholder text with your actual keys. See [`.env.example`](.env.example) for all options (`ALLOWED_CHAT_IDS`, `DATA_DIR`, Honeybadger, `LOG_FORMAT`, etc.). `ALLOWED_CHAT_IDS` can be left empty or set to `0` for public use. `DATA_DIR` defaults to `./data` for SQLite watchlists/alerts.

   **One poller per token:** Telegram allows only one `getUpdates` long-poller per bot token. Do not run the bot locally with the production `TELEGRAM_BOT_TOKEN` while Railway (or another deploy) is already polling. Prefer a separate BotFather bot for local development.
5. Run the bot:
   ```bash
   python -m bot.main
   ```

## Versioning and Releases

This project uses Release Please with Conventional Commits to automate semantic versioning.

- `fix:` commits create patch releases.
- `feat:` commits create minor releases.
- `feat!:`, `fix!:`, or `BREAKING CHANGE:` create breaking releases.

The current version is tracked in `version.txt`, `pyproject.toml`, and `bot/__init__.py`. When a release PR is merged, Release Please updates `CHANGELOG.md`, bumps those version files, creates a GitHub Release, and tags the release as `vX.Y.Z`.

See [docs/release.md](docs/release.md) for the full release process.

## Running Tests

1. Install testing requirements:
   ```bash
   pip install -r requirements-test.txt
   ```
2. Run tests via pytest (ensure your PYTHONPATH points to the project root):
   ```bash
   PYTHONPATH=. pytest tests/
   ```

## Railway Deployment

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/6k39OM?referralCode=cPw57c&utm_medium=integration&utm_source=template&utm_campaign=generic)

This project is ready to be deployed on [Railway](https://railway.app/). Railway will automatically detect this as a Python application due to the presence of `bot/main.py` and `requirements.txt`.

1. Push this repository to GitHub.
2. Go to Railway and create a new project from your GitHub repository.
3. In the Railway dashboard, go to the **Variables** section of your new service.
4. Add the following environment variables (which you also put into GitHub Secrets):
   - `TELEGRAM_BOT_TOKEN`
   - `HONEYBADGER_API_KEY` (optional; enables Honeybadger error reporting)
   - `HONEYBADGER_ENVIRONMENT` (optional; defaults to Railway’s environment name or `development`)
   - `ALLOWED_CHAT_IDS` (optional, to restrict bot access to specific chat IDs. Set to `0` or leave empty to allow anyone to talk with the bot)
   - `DATA_DIR` (optional; defaults to `/app/data` in Docker)
   - `LOG_FORMAT` (optional; `json` or `text`. On Railway, logs default to JSON when `RAILWAY_ENVIRONMENT` is set)
5. Mount a Railway volume at `/app/data` (or whatever path you set for `DATA_DIR`) so SQLite watchlists and alerts survive redeploys.
6. Keep **replicas / instances at 1** for this service, and use this token on only one Railway service. A second poller (local bot, duplicate service, or scale > 1) causes Telegram `Conflict: terminated by other getUpdates request` errors.
7. Railway will automatically build and deploy your bot.
