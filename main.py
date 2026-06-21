import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    welcome_message = (
        f"Hi {user.first_name}!\n\n"
        "I am a financial bot. Here are the commands you can use:\n"
        "/stock <ticker> - Get the current price of a stock (e.g., /stock AAPL)\n"
        "/crypto <symbol> - Get the current price of a cryptocurrency (e.g., /crypto BTC/USD)"
    )
    await update.message.reply_text(welcome_message)

def get_price(symbol: str) -> str:
    """Helper function to get the current price from TwelveData API."""
    if not TWELVEDATA_API_KEY:
        return "Error: Twelve Data API Key is not configured."

    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={TWELVEDATA_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if "price" in data:
            price = round(float(data["price"]), 2)
            return f"The current price of {symbol.upper()} is ${price}"
        elif "status" in data and data["status"] == "error":
            return f"Error: {data.get('message', 'Unknown error from TwelveData')}"
        else:
            return f"Could not find price for {symbol.upper()}"

    except Exception as e:
        logger.error(f"Error fetching data from TwelveData: {e}")
        return "Sorry, I couldn't fetch the data right now. Please try again later."

async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get the current price of a stock."""
    if not context.args:
        await update.message.reply_text("Please provide a stock ticker. Example: /stock AAPL")
        return

    ticker = context.args[0]
    await update.message.reply_text(f"Fetching price for stock: {ticker.upper()}...")

    result = get_price(ticker)
    await update.message.reply_text(result)

async def crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get the current price of a cryptocurrency."""
    if not context.args:
        await update.message.reply_text("Please provide a crypto symbol. Example: /crypto BTC/USD")
        return

    symbol = context.args[0]
    # Crypto pairs often need /USD appended if not provided
    if '/' not in symbol:
        symbol = f"{symbol}/USD"

    await update.message.reply_text(f"Fetching price for crypto: {symbol.upper()}...")

    result = get_price(symbol)
    await update.message.reply_text(result)

def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in the environment variables.")
        return

    # Create the Application and pass it your bot's token.
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stock", stock))
    application.add_handler(CommandHandler("crypto", crypto))

    # Run the bot until the user presses Ctrl-C
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
