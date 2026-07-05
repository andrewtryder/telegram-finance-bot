<!-- OpenGraph / Social Preview -->
<meta property="og:title" content="Telegram Financial Bot" />
<meta property="og:description" content="A Telegram bot for real-time stock, crypto, and index prices via yfinance and Twelve Data." />
<meta property="og:image" content="https://raw.githubusercontent.com/andrewtryder/telegram-stock-price-bot/main/docs/screenshot.png" />
<meta property="og:type" content="website" />
<meta property="og:url" content="https://github.com/andrewtryder/telegram-stock-price-bot" />

# Telegram Financial Bot

[![CI/CD Pipeline](https://github.com/andrewtryder/telegram-stock-price-bot/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/andrewtryder/telegram-stock-price-bot/actions/workflows/ci-cd.yml)
[![Release Please](https://github.com/andrewtryder/telegram-stock-price-bot/actions/workflows/release-please.yml/badge.svg)](https://github.com/andrewtryder/telegram-stock-price-bot/actions/workflows/release-please.yml)
[![Docker Image Publish](https://github.com/andrewtryder/telegram-stock-price-bot/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/andrewtryder/telegram-stock-price-bot/actions/workflows/docker-publish.yml)
[![Docker Registry](https://img.shields.io/badge/docker-GHCR-blue?style=flat&logo=docker&logoColor=white)](https://github.com/andrewtryder/telegram-stock-price-bot/pkgs/container/telegram-stock-price-bot)
[![License](https://img.shields.io/github/license/andrewtryder/telegram-stock-price-bot)](https://github.com/andrewtryder/telegram-stock-price-bot/blob/main/LICENSE)

A Telegram bot that fetches stock, crypto, and index prices via yfinance (Yahoo Finance), with symbol search powered by the Twelve Data API.

## Preview

![Telegram Financial Bot in action](https://raw.githubusercontent.com/andrewtryder/telegram-stock-price-bot/main/docs/screenshot.png)

## Features

- `/start` - Displays a welcome message and lists available commands.
- `/stock <ticker>` - Fetches the current price of a stock (e.g., `/stock AAPL`).
- `/stockinfo <ticker>` - Fetches company information such as sector, industry, P/E ratio, dividend yield, and 52-week range (e.g., `/stockinfo AAPL`).
- `/stocknews <ticker>` - Fetches recent news headlines for a stock (e.g., `/stocknews AAPL`).
- `/marketcap <ticker>` - Fetches a company's market capitalization (e.g., `/marketcap AAPL`).
- `/crypto <symbol>` - Fetches the current price of a cryptocurrency (e.g., `/crypto BTC` or `/crypto ETH`).
- `/indices` - Fetches current levels of major market indices (S&P 500, Dow Jones, Nasdaq Composite).
- `/search <query>` - Search for a symbol via Twelve Data (e.g., `/search Apple`).

In private chats, `/start` and `/help` show a reply keyboard with quick command buttons. In groups, commands are available via Telegram's native `/` menu (registered on bot startup).

## Group Chats

This bot is designed for command-only use in groups:

- **Command menu:** On startup the bot registers `/` commands via `setMyCommands` — use the menu button next to the message field in any group.
- **Privacy mode (recommended):** In [@BotFather](https://t.me/BotFather), send `/setprivacy`, select your bot, and choose **Enable**. The bot will only receive messages that start with `/`, @mention the bot, or reply to the bot. This is enabled by default for new bots.
- **No reply keyboard in groups:** `/start` and `/help` omit the persistent keyboard in groups and supergroups to avoid cluttering shared chats.
- **Code-level filter:** Non-command messages in groups are ignored as a fallback if privacy mode is disabled in BotFather.

## Prerequisites

To run this bot locally or in production, you will need:

1. **Telegram Bot Token**:
   - Go to Telegram and search for the `@BotFather` bot.
   - Send `/newbot` and follow the instructions to create a new bot.
   - Copy the API token provided at the end.

2. **Twelve Data API Key** (required for `/search` only):
   - Go to [Twelve Data](https://twelvedata.com/) and sign up for a free account.
   - Navigate to your dashboard to find your API key.

3. **Allowed Chat IDs** (optional):
   - Set `ALLOWED_CHAT_IDS` to a comma-separated list of allowed Telegram user or group IDs (e.g., `12345678,-10012345678`) to restrict bot access.
   - If not set, the bot responds to all incoming commands.

## Docker

The easiest way to run the bot. Pre-built Docker images (`linux/amd64`) are published automatically to the GitHub Container Registry.

- Pushes to `main` publish `latest` and traceable SHA tags.
- Release Please releases publish semantic version tags such as `0.2.0`, `0.2`, and `0`.

### Pull and run from GHCR

```bash
# Pull the latest image
docker pull ghcr.io/andrewtryder/telegram-stock-price-bot:latest

# Or pin a released version
docker pull ghcr.io/andrewtryder/telegram-stock-price-bot:0.1.0

# Run using your .env file
docker run --env-file .env ghcr.io/andrewtryder/telegram-stock-price-bot:latest
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
```

Then:

```bash
docker compose up -d
```

### Build locally from source

```bash
docker build -t telegram-stock-price-bot .
docker run --env-file .env telegram-stock-price-bot
```

## Local Setup

1. Clone this repository.
2. Create a virtual environment and activate it:
   ```bash
   python3 -m venv venv
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
   Open `.env` and replace the placeholder text with your actual keys. `ALLOWED_CHAT_IDS` can be left empty for public use.
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
   - `TWELVEDATA_API_KEY` (for `/search` only)
   - `ALLOWED_CHAT_IDS` (optional, to restrict bot access to specific chat IDs)
5. Railway will automatically build and deploy your bot.
