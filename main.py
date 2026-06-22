import os
import logging
import httpx
import time
import asyncio
import yfinance as yf
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ChatAction
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

# API Cache (URL -> (timestamp, data))
API_CACHE = {}
CACHE_TTL = 600  # 10 minutes

async def fetch_with_cache(url: str) -> dict:
    """Fetch URL with a 10-minute in-memory cache using async httpx."""
    current_time = time.time()

    # Check cache
    if url in API_CACHE:
        timestamp, data = API_CACHE[url]
        if current_time - timestamp < CACHE_TTL:
            logger.info(f"⚡ Cache HIT for URL: {url.split('?')[0]} (params hidden)")
            return data

    # Cache MISS - fetch async
    logger.info(f"🐢 Cache MISS for URL: {url.split('?')[0]} - fetching from API")
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

        # Save to cache
        API_CACHE[url] = (current_time, data)
        return data


def get_help_text(first_name: str = "there") -> str:
    """Returns the standard help/welcome message."""
    return (
        f"Hi {first_name}!\n\n"
        "I am a financial bot. Here are the commands you can use:\n"
        "📊 `/stock <ticker>` - Get the current price of a stock (e.g., /stock AAPL)\n"
        "🪙 `/crypto <symbol>` - Get the current price of a crypto (e.g., /crypto BTC)\n"
        "🔍 `/search <query>` - Search for a symbol (e.g., /search Apple)\n"
        "📉 `/indices` (or `/indicies`) - Get the current levels of major market indices\n"
        "❓ `/help` - Show this message again"
    )


def get_reply_keyboard():
    keyboard = [
        [KeyboardButton("/stock AAPL"), KeyboardButton("/crypto BTC")],
        [KeyboardButton("/indices"), KeyboardButton("/help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    logger.info(f"User {update.effective_user.username or update.effective_user.first_name} ran /start")
    await update.message.reply_text(
        get_help_text(update.effective_user.first_name),
        parse_mode='Markdown',
        reply_markup=get_reply_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a list of commands when /help is issued."""
    logger.info(f"User {update.effective_user.username or update.effective_user.first_name} ran /help")
    await update.message.reply_text(
        get_help_text(update.effective_user.first_name),
        parse_mode='Markdown',
        reply_markup=get_reply_keyboard()
    )

def _get_yf_info(symbol: str):
    """Synchronous helper to fetch yfinance data."""
    ticker = yf.Ticker(symbol)
    return ticker.info

async def get_quote_formatted(symbol: str) -> str:
    """Helper function to get detailed quote data from yfinance."""
    try:
        # yfinance is synchronous, so we run it in a thread to avoid blocking the event loop
        info = await asyncio.to_thread(_get_yf_info, symbol)
        
        if not info or 'regularMarketPrice' not in info:
            return f"Could not find quote data for {symbol.upper()}"

        name = info.get("shortName") or info.get("longName") or symbol.upper()
        price = info.get("regularMarketPrice")
        change = info.get("regularMarketChange", 0)
        pct_change = info.get("regularMarketChangePercent", 0)
        currency = info.get("currency", "USD")

        sign = "+" if change >= 0 else ""

        return (
            f"📈 **{name} ({symbol.upper()})**\n"
            f"Price: {price:,.2f} {currency}\n"
            f"Change: {sign}{change:,.2f} ({sign}{pct_change:.2f}%)"
        )

    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return "Sorry, I couldn't fetch the data right now. Please try again later."

async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get the current price of a stock."""
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    if not context.args:
        await update.message.reply_text("Please provide a stock ticker. Example: `/stock AAPL`", parse_mode='Markdown')
        return

    ticker = context.args[0]
    result = await get_quote_formatted(ticker)
    await update.message.reply_text(result, parse_mode='Markdown')

async def crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get the current price of a cryptocurrency."""
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    if not context.args:
        await update.message.reply_text("Please provide a crypto symbol. Example: `/crypto BTC`", parse_mode='Markdown')
        return

    symbol = context.args[0].upper()

    # Convert TwelveData style or plain symbols to yfinance style
    # yfinance uses DASH for crypto pairs, e.g., BTC-USD
    if '/' in symbol:
        symbol = symbol.replace('/', '-')
    elif '-' not in symbol:
        symbol = f"{symbol}-USD"

    result = await get_quote_formatted(symbol)
    await update.message.reply_text(result, parse_mode='Markdown')

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for a stock, crypto, or ETF symbol using TwelveData."""
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    if not context.args:
        await update.message.reply_text("Please provide a search term. Example: `/search Vanguard`", parse_mode='Markdown')
        return

    if not TWELVEDATA_API_KEY:
        await update.message.reply_text("Error: Twelve Data API Key is not configured for search.", parse_mode='Markdown')
        return

    query = " ".join(context.args)
    url = f"https://api.twelvedata.com/symbol_search?symbol={query}&apikey={TWELVEDATA_API_KEY}"
    
    try:
        data = await fetch_with_cache(url)
        
        if "data" in data and len(data["data"]) > 0:
            results = data["data"][:5] # Limit to Top 5 results
            text = f"🔍 **Search results for '{query}':**\n\n"
            for item in results:
                sym = item.get('symbol', 'N/A')
                name = item.get('instrument_name', 'N/A')
                exch = item.get('exchange', 'N/A')
                type_ = item.get('instrument_type', 'N/A')
                text += f"• **{sym}** - {name} ({exch}, {type_})\n"
            await update.message.reply_text(text, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"No results found for '{query}'.")
    except Exception as e:
        logger.error(f"Error searching for {query}: {e}")
        await update.message.reply_text("Sorry, the search function is currently unavailable.")

async def indices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get the current price of major indices using yfinance."""
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    # Real index symbols for yfinance
    index_mapping = {
        "^GSPC": "S&P 500",
        "^DJI": "Dow Jones Industrial Average",
        "^IXIC": "Nasdaq Composite"
    }
    
    response_text = "📊 **Major Market Indices**\n\n"
    
    try:
        for symbol, readable_name in index_mapping.items():
            info = await asyncio.to_thread(_get_yf_info, symbol)
            
            if info and 'regularMarketPrice' in info:
                price = info["regularMarketPrice"]
                pct_change = info.get("regularMarketChangePercent", 0)
                sign = "+" if pct_change >= 0 else ""
                response_text += f"• **{readable_name}**: {price:,.2f} ({sign}{pct_change:.2f}%)\n"
            else:
                response_text += f"• **{readable_name}**: Data unavailable\n"
                
    except Exception as e:
        logger.error(f"Error fetching indices: {e}")
        response_text = "Sorry, I couldn't fetch the indices right now."

    await update.message.reply_text(response_text, parse_mode='Markdown')

def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in the environment variables.")
        return

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stock", stock))
    application.add_handler(CommandHandler("crypto", crypto))
    application.add_handler(CommandHandler("search", search))
    
    # Passing a tuple lets one function handle multiple spellings of the command!
    application.add_handler(CommandHandler(("indices", "indicies"), indices))

    logger.info("Starting bot... Waiting for commands.")
    application.run_polling()

if __name__ == '__main__':
    main()
