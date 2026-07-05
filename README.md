# Telegram Financial Bot

A Telegram bot that fetches stock, crypto, and index prices via yfinance (Yahoo Finance), with symbol search powered by the Twelve Data API.

## Features

- `/start` - Displays a welcome message and lists available commands.
- `/stock <ticker>` - Fetches the current price of a given stock (e.g., `/stock AAPL`).
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
   Open `.env` and replace the placeholder text with your actual keys.
5. Run the bot:
   ```bash
   python -m bot.main
   ```

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
5. Railway will automatically build and deploy your bot.
