import os
import logging
from twelvedata import TDClient
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
td_client = TDClient(apikey=TWELVEDATA_API_KEY) if TWELVEDATA_API_KEY else None

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
    BotCommand("stockinfo", "Get detailed stock info"),
    BotCommand("stocknews", "Get recent news for a stock"),
    BotCommand("marketcap", "Get market cap for a stock"),
    BotCommand("help", "Show available commands"),
]

GROUP_COMMANDS = [
    BotCommand("stock", "Get a stock price (e.g. /stock AAPL)"),
    BotCommand("crypto", "Get a crypto price (e.g. /crypto BTC)"),
    BotCommand("search", "Search for a symbol"),
    BotCommand("indices", "Major market index levels"),
    BotCommand("stockinfo", "Get detailed stock info"),
    BotCommand("stocknews", "Get recent news for a stock"),
    BotCommand("marketcap", "Get market cap for a stock"),
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


def get_help_text(first_name: str = "there") -> str:
    """Returns the standard help/welcome message."""
    return (
        f"Hi {first_name}!\n\n"
        "I am a financial bot. Here are the commands you can use:\n"
        "📊 `/stock <ticker>` - Get the current price of a stock (e.g., /stock AAPL)\n"
        "🪙 `/crypto <symbol>` - Get the current price of a crypto (e.g., /crypto BTC)\n"
        "🔍 `/search <query>` - Search for a symbol (e.g., /search Apple)\n"
        "📉 `/indices` (or `/indicies`) - Get the current levels of major market indices\n"
        "ℹ️ `/stockinfo <ticker>` - Get detailed info for a stock\n"
        "📰 `/stocknews <ticker>` - Get recent news for a stock\n"
        "💰 `/marketcap <ticker>` - Get market cap for a stock\n"
        "❓ `/help` - Show this message again"
    )


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
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a list of commands when /help is issued."""
    logger.info(f"User {update.effective_user.username or update.effective_user.first_name} ran /help")
    await update.message.reply_text(
        get_help_text(update.effective_user.first_name),
        parse_mode='Markdown'
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

def _format_large_number(num: float) -> str:
    if num is None:
        return "N/A"
    try:
        num = float(num)
        if num >= 1e12:
            return f"${num/1e12:.2f}T"
        elif num >= 1e9:
            return f"${num/1e9:.2f}B"
        elif num >= 1e6:
            return f"${num/1e6:.2f}M"
        else:
            return f"${num:,.2f}"
    except (ValueError, TypeError):
        return "N/A"

def _truncate_text(text: str, max_length: int = 400) -> str:
    if not text:
        return "N/A"
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(' ', 1)[0] + "..."

async def stockinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    if not context.args:
        await update.message.reply_text("Please provide a stock ticker. Example: `/stockinfo AAPL`", parse_mode='Markdown')
        return

    ticker = context.args[0]
    yfinance_symbol = to_yfinance_stock(ticker)

    try:
        info = await _get_yfinance_info(yfinance_symbol)

        name = info.get("shortName") or info.get("longName") or yfinance_symbol
        sector = info.get("sector", "N/A")
        industry = info.get("industry", "N/A")
        market_cap = _format_large_number(info.get("marketCap"))
        pe_ratio = info.get("trailingPE") or info.get("forwardPE")
        pe_str = f"{pe_ratio:.2f}" if isinstance(pe_ratio, (int, float)) else "N/A"

        div_yield = info.get("dividendYield")
        div_str = f"{div_yield * 100:.2f}%" if isinstance(div_yield, (int, float)) else "N/A"

        high52 = info.get("fiftyTwoWeekHigh")
        high52_str = f"${high52:,.2f}" if isinstance(high52, (int, float)) else "N/A"

        low52 = info.get("fiftyTwoWeekLow")
        low52_str = f"${low52:,.2f}" if isinstance(low52, (int, float)) else "N/A"

        summary = _truncate_text(info.get("longBusinessSummary", "No summary available."))

        lines = [
            f"ℹ️ **{name} ({yfinance_symbol})**",
            f"**Sector:** {sector}",
            f"**Industry:** {industry}",
            "",
            f"**Market Cap:** {market_cap}",
            f"**P/E Ratio:** {pe_str}",
            f"**Dividend Yield:** {div_str}",
            f"**52W High/Low:** {high52_str} / {low52_str}",
            "",
            f"**Summary:** {summary}"
        ]

        await update.message.reply_text("\n".join(lines), parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error fetching info for {yfinance_symbol}: {e}")
        await update.message.reply_text("Sorry, I couldn't fetch info for that symbol right now.")

def _fetch_yfinance_news(symbol: str) -> list:
    import yfinance as yf
    try:
        t = yf.Ticker(symbol)
        return t.news
    except Exception as e:
        logger.error(f"yfinance news error for {symbol}: {e}")
        return []

async def stocknews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    if not context.args:
        await update.message.reply_text("Please provide a stock ticker. Example: `/stocknews AAPL`", parse_mode='Markdown')
        return

    ticker = context.args[0]
    yfinance_symbol = to_yfinance_stock(ticker)

    try:
        news_items = await asyncio.to_thread(_fetch_yfinance_news, yfinance_symbol)
        if not news_items:
            await update.message.reply_text(f"No recent news found for {yfinance_symbol}.")
            return

        lines = [f"📰 **Recent news for {yfinance_symbol}**", ""]
        for item in news_items[:5]:
            content = item.get('content', {}) if 'content' in item else item
            title = content.get('title', 'No Title')

            url = ""
            if 'clickThroughUrl' in content:
                url = content['clickThroughUrl'].get('url', '')
            elif 'link' in item:
                url = item['link']

            lines.append(f"• [{title}]({url})")

        await update.message.reply_text("\n".join(lines), parse_mode='Markdown', disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error fetching news for {yfinance_symbol}: {e}")
        await update.message.reply_text("Sorry, I couldn't fetch news for that symbol right now.")

async def marketcap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    if not context.args:
        await update.message.reply_text("Please provide a stock ticker. Example: `/marketcap AAPL`", parse_mode='Markdown')
        return

    ticker = context.args[0]
    yfinance_symbol = to_yfinance_stock(ticker)

    try:
        info = await _get_yfinance_info(yfinance_symbol)

        name = info.get("shortName") or info.get("longName") or yfinance_symbol
        market_cap = _format_large_number(info.get("marketCap"))

        text = f"💰 **{name} ({yfinance_symbol})** Market Cap: {market_cap}"
        await update.message.reply_text(text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error fetching market cap for {yfinance_symbol}: {e}")
        await update.message.reply_text("Sorry, I couldn't fetch data for that symbol right now.")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for a stock, crypto, or ETF symbol."""
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    if not context.args:
        await update.message.reply_text("Please provide a search term. Example: `/search Vanguard`", parse_mode='Markdown')
        return

    if not td_client:
        await update.message.reply_text("Error: Twelve Data API Key is not configured.")
        return

    query = " ".join(context.args)
    
    try:
        data = await asyncio.to_thread(lambda: td_client.symbol_search(symbol=query).as_json())
        
        # Debug logging
        logger.info(f"Raw Search API Response for '{query}' retrieved.")

        if data and len(data) > 0:
            results = data[:5] # Limit to Top 5 results
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
    application.add_handler(CommandHandler("stockinfo", stockinfo))
    application.add_handler(CommandHandler("stocknews", stocknews))
    application.add_handler(CommandHandler("marketcap", marketcap))
    
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
