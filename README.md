<!-- OpenGraph / Social Preview -->
<meta property="og:title" content="Telegram Financial Bot" />
<meta property="og:description" content="A Telegram bot for stock, crypto, and index quotes, plus watchlists, charts, and price alerts via yfinance." />
<meta property="og:image" content="https://raw.githubusercontent.com/andrewtryder/telegram-stock-price-bot/main/docs/screenshot.png" />
<meta property="og:type" content="website" />
<meta property="og:url" content="https://github.com/andrewtryder/telegram-stock-price-bot" />

# Telegram Financial Bot

[![CI/CD Pipeline](https://github.com/andrewtryder/telegram-stock-price-bot/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/andrewtryder/telegram-stock-price-bot/actions/workflows/ci-cd.yml)
[![License](https://img.shields.io/github/license/andrewtryder/telegram-stock-price-bot)](https://github.com/andrewtryder/telegram-stock-price-bot/blob/main/LICENSE)

A Telegram bot for stock, crypto, and index quotes via yfinance (Yahoo Finance), with personal watchlists, charts, and chat-owned price alerts.

![Telegram Financial Bot in action](https://raw.githubusercontent.com/andrewtryder/telegram-stock-price-bot/main/docs/screenshot.png)

## Features

- `/stock` `/stockinfo` `/stocknews` `/marketcap` — quotes and company data
- `/crypto` `/indices` — crypto pairs and major market indices
- `/search` — find Yahoo Finance symbols
- `/compare` — side-by-side quotes (2–4 tickers)
- `/chart` — closing-price chart PNG
- `/watchlist` — personal list (max 10), shared across your chats
- `/alert` — one-shot price alerts (max 20 per chat); chat-owned — fire into the chat; anyone there can list or remove

## Run

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. `cp .env.example .env` and set `TELEGRAM_BOT_TOKEN` (see [`.env.example`](.env.example) for optional vars).
3. Run with Docker (volume keeps watchlists/alerts):

```bash
docker pull ghcr.io/andrewtryder/telegram-stock-price-bot:latest
docker run -v bot-data:/app/data --env-file .env ghcr.io/andrewtryder/telegram-stock-price-bot:latest
```

Or locally (Python 3.12+):

```bash
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m bot.main
```

Use one poller per bot token — don’t run local and production against the same token at once.

## Deploy on Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/6k39OM?referralCode=cPw57c&utm_medium=integration&utm_source=template&utm_campaign=generic)

1. Deploy from this repo (or the button above).
2. Set `TELEGRAM_BOT_TOKEN` (and any optional vars from [`.env.example`](.env.example)).
3. Mount a volume at `/app/data` so SQLite data survives redeploys.
4. Keep replicas at **1** — only one poller per token.
