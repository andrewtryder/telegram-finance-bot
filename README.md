# Telegram Financial Bot

A basic Telegram bot that fetches current stock and cryptocurrency prices using the Twelve Data API.

## Features

- `/start` - Displays a welcome message and lists available commands.
- `/stock <ticker>` - Fetches the current price of a given stock (e.g., `/stock AAPL`).
- `/crypto <symbol>` - Fetches the current price of a cryptocurrency (e.g., `/crypto BTC/USD` or `/crypto ETH`).

## Prerequisites

To run this bot locally or in production, you will need two pieces of information:

1. **Telegram Bot Token**:
   - Go to Telegram and search for the `@BotFather` bot.
   - Send `/newbot` and follow the instructions to create a new bot.
   - Copy the API token provided at the end.

2. **Twelve Data API Key**:
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
   python main.py
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

This project is ready to be deployed on [Railway](https://railway.app/). Railway will automatically detect this as a Python application due to the presence of `main.py` and `requirements.txt`.

1. Push this repository to GitHub.
2. Go to Railway and create a new project from your GitHub repository.
3. In the Railway dashboard, go to the **Variables** section of your new service.
4. Add the following environment variables (which you also put into GitHub Secrets):
   - `TELEGRAM_BOT_TOKEN`
   - `TWELVEDATA_API_KEY`
5. Railway will automatically build and deploy your bot.
