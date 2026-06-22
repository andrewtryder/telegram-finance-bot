import os
import logging
import httpx
import time
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
import yfinance as yf
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
)
from telegram.constants import ChatAction, ChatType
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from symbols import to_yfinance_stock, to_yfinance_crypto, crypto_display_symbol

# Load environment variables
load_dotenv()

# Configure logging (Set to INFO, but we manually log all critical actions)
# If you want to see deep library debug data, change logging.INFO to logging.DEBUG
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
# Quote cache (yfinance symbol -> (timestamp, info dict))
QUOTE_CACHE = {}
CACHE_TTL = 600  # 10 minutes

INDEX_MAPPING = {
    "^GSPC": "S&P 500",
    "^DJI": "Dow Jones",
    "^IXIC": "Nasdaq Composite",
}

BOT_COMMANDS = [
    BotCommand("start", "Show welcome message"),
    BotCommand("stock", "Get a stock price (e.g. /stock AAPL)"),
    BotCommand("crypto", "Get a crypto price (e.g. /crypto BTC)"),
    BotCommand("search", "Search for a symbol"),
    BotCommand("indices", "Major market index levels"),
    BotCommand("help", "Show available commands"),
]

GROUP_COMMANDS = [
    BotCommand("stock", "Get a stock price (e.g. /stock AAPL)"),
    BotCommand("crypto", "Get a crypto price (e.g. /crypto BTC)"),
    BotCommand("search", "Search for a symbol"),
    BotCommand("indices", "Major market index levels"),
    BotCommand("help", "Show available commands"),
]

# Ignore non-command messages in groups (defense-in-depth alongside BotFather privacy mode).
GROUP_PRIVACY_FILTER = filters.ChatType.GROUPS & ~filters.COMMAND & ~filters.StatusUpdate.ALL


def _fetch_yfinance_info(yfinance_symbol: str) -> dict:
    ticker = yf.Ticker(yfinance_symbol)
    info = ticker.info
    logger.info(f"Raw yfinance info for {yfinance_symbol}: {info}")
    return info


async def _get_yfinance_info(yfinance_symbol: str) -> dict:
    current_time = time.time()

    if yfinance_symbol in QUOTE_CACHE:
        timestamp, data = QUOTE_CACHE[yfinance_symbol]
        if current_time - timestamp < CACHE_TTL:
            logger.info(f"⚡ Cache HIT for symbol: {yfinance_symbol}")
            return data

    logger.info(f"🐢 Cache MISS for symbol: {yfinance_symbol} - fetching from yfinance")
    info = await asyncio.to_thread(_fetch_yfinance_info, yfinance_symbol)
    QUOTE_CACHE[yfinance_symbol] = (current_time, info)
    return info


def _format_market_time(info: dict) -> str:
    market_time = info.get("regularMarketTime")
    if market_time:
        return datetime.fromtimestamp(market_time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return "Unknown time"


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


def get_reply_markup_for_chat(chat_type: str):
    if chat_type == ChatType.PRIVATE:
        return get_reply_keyboard()
    return None


async def setup_commands(application: Application) -> None:
    bot = application.bot
    await bot.set_my_commands(BOT_COMMANDS, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(GROUP_COMMANDS, scope=BotCommandScopeAllGroupChats())
    logger.info("Registered bot command menu for private and group chats")


async def _ignore_non_command_group_messages(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Drop non-command group messages when privacy mode is disabled in BotFather."""
    logger.debug(
        "Ignored non-command message in group chat %s",
        update.effective_chat.id,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    logger.info(f"User {update.effective_user.username or update.effective_user.first_name} ran /start")
    await update.message.reply_text(
        get_help_text(update.effective_user.first_name),
        parse_mode='Markdown',
        reply_markup=get_reply_markup_for_chat(update.effective_chat.type)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a list of commands when /help is issued."""
    logger.info(f"User {update.effective_user.username or update.effective_user.first_name} ran /help")
    await update.message.reply_text(
        get_help_text(update.effective_user.first_name),
        parse_mode='Markdown',
        reply_markup=get_reply_markup_for_chat(update.effective_chat.type)
    )

async def get_quote_formatted(yfinance_symbol: str, display_symbol: str | None = None) -> str:
    """Helper function to get detailed quote data from yfinance."""
    if display_symbol is None:
        display_symbol = yfinance_symbol.upper()

    try:
        info = await _get_yfinance_info(yfinance_symbol)

        price = info.get("regularMarketPrice")
        if price is None:
            return f"Could not find quote data for {display_symbol}"

        name = info.get("shortName") or info.get("longName") or display_symbol
        change = float(info.get("regularMarketChange") or 0)
        pct_change = float(info.get("regularMarketChangePercent") or 0)
        time_reported = _format_market_time(info)

        sign = "+" if change >= 0 else ""

        return (
            f"📈 **{name} ({display_symbol})**\n"
            f"Price: ${price:,.2f}\n"
            f"Change: {sign}{change:,.2f} ({sign}{pct_change:.2f}%)\n"
            f"🕒 Last reported: {time_reported}"
        )

    except Exception as e:
        logger.error(f"Network/Code Error fetching data for {yfinance_symbol}: {e}")
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
    yfinance_symbol = to_yfinance_stock(ticker)
    result = await get_quote_formatted(yfinance_symbol, yfinance_symbol)
    await update.message.reply_text(result, parse_mode='Markdown')

async def crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get the current price of a cryptocurrency."""
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    if not context.args:
        await update.message.reply_text("Please provide a crypto symbol. Example: `/crypto BTC`", parse_mode='Markdown')
        return

    symbol = context.args[0]
    yfinance_symbol = to_yfinance_crypto(symbol)
    display_symbol = crypto_display_symbol(symbol)
    result = await get_quote_formatted(yfinance_symbol, display_symbol)
    await update.message.reply_text(result, parse_mode='Markdown')

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for a stock, crypto, or ETF symbol."""
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    if not context.args:
        await update.message.reply_text("Please provide a search term. Example: `/search Vanguard`", parse_mode='Markdown')
        return

    if not TWELVEDATA_API_KEY:
        await update.message.reply_text("Error: Twelve Data API Key is not configured.")
        return

    query = " ".join(context.args)
    url = f"https://api.twelvedata.com/symbol_search?symbol={query}&apikey={TWELVEDATA_API_KEY}"
    
    try:
        data = await fetch_with_cache(url)
        
        # Debug logging
        logger.info(f"Raw Search API Response for '{query}': {data}")

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
    """Get the current levels of major market indices."""
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    response_text = "📊 **Major Market Indices**\n\n"

    try:
        fetch_tasks = [
            _get_yfinance_info(symbol) for symbol in INDEX_MAPPING
        ]
        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        for (symbol, readable_name), info in zip(INDEX_MAPPING.items(), results):
            if isinstance(info, Exception):
                logger.error(f"Error fetching index {symbol}: {info}")
                response_text += f"• **{readable_name}**: Data unavailable\n"
                continue

            price = info.get("regularMarketPrice")
            if price is None:
                response_text += f"• **{readable_name}**: Data unavailable\n"
                continue

            pct_change = float(info.get("regularMarketChangePercent") or 0)
            sign = "+" if pct_change >= 0 else ""
            response_text += f"• **{readable_name}**: {price:,.2f} ({sign}{pct_change:.2f}%)\n"

    except Exception as e:
        logger.error(f"Error fetching indices: {e}")
        response_text = "Sorry, I couldn't fetch the indices right now."

    await update.message.reply_text(response_text, parse_mode='Markdown')

def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in the environment variables.")
        return

    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(setup_commands)
        .build()
    )

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stock", stock))
    application.add_handler(CommandHandler("crypto", crypto))
    application.add_handler(CommandHandler("search", search))
    
    # Passing a tuple lets one function handle multiple spellings of the command!
    application.add_handler(CommandHandler(("indices", "indicies"), indices))

    # Groups: only respond to /commands (matches BotFather privacy mode behavior).
    application.add_handler(
        MessageHandler(GROUP_PRIVACY_FILTER, _ignore_non_command_group_messages),
        group=1,
    )

    logger.info("Starting bot... Waiting for commands.")
    application.run_polling()

if __name__ == '__main__':
    main()
