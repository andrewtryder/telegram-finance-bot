import html

from telegram import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ChatType
from telegram.ext import Application, ContextTypes

from bot.config import logger


def get_help_text(first_name: str = "there", specific_command: str = None) -> str:
    escaped_name = html.escape(first_name)

    if specific_command == "stock":
        return (
            "<b>/stock &lt;ticker&gt;</b>\n"
            "Shows a quote snapshot for a stock, ETF, fund, or Yahoo Finance-compatible symbol.\n\n"
            "Examples:\n"
            "  /stock AAPL\n"
            "  /stock MSFT\n"
            "  /stock BRK.B\n"
            "  /stock ^GSPC\n\n"
            "Default output:\n"
            "  • Current price\n"
            "  • Change today in points and %\n"
            "  • Previous close and open\n"
            "  • Day range\n"
            "  • 5-day/week range\n"
            "  • 52-week/year range\n"
            "  • Volume and average volume\n"
            "  • Market cap\n"
            "  • Exchange, currency, and quote timestamp\n\n"
            "Data sources:\n"
            "  • fast_info for current quote fields where available\n"
            '  • history(period="5d") for week range\n'
            '  • fast_info or history(period="1y") for 52-week range\n\n'
            "Notes:\n"
            "  Data may be delayed or unavailable for some symbols."
        )
    elif specific_command == "crypto":
        return (
            "<b>/crypto &lt;symbol&gt;</b>\n"
            "Shows a quote snapshot for a crypto pair.\n\n"
            "Examples:\n"
            "  /crypto BTC\n"
            "  /crypto ETH\n"
            "  /crypto BTC/USD\n"
            "  /crypto SOL-USD\n\n"
            "Default output:\n"
            "  • Current price\n"
            "  • Change today in points and %\n"
            "  • Day range\n"
            "  • 5-day/week range\n"
            "  • 52-week/year range\n"
            "  • Volume when available\n"
            "  • Currency and timestamp\n\n"
            "Notes:\n"
            "  Bare symbols default to USD, so /crypto BTC means BTC-USD."
        )
    elif specific_command == "indices" or specific_command == "indicies":
        return (
            "<b>/indices</b>\n"
            "Shows current levels and ranges of major market indices (S&P 500, Dow Jones, Nasdaq).\n\n"
            "Default output:\n"
            "  • Current level\n"
            "  • Change today in points and %\n"
            "  • Day range\n"
            "  • 5-day/week range\n"
            "  • 52-week/year range"
        )
    elif specific_command == "stockinfo":
        return (
            "<b>/stockinfo &lt;ticker&gt;</b>\n"
            "Fetches company profile information including sector, "
            "industry, description, website, and basic valuation metrics."
        )
    elif specific_command == "stocknews":
        return "<b>/stocknews &lt;ticker&gt;</b>\nFetches the latest 5 news headlines for a given stock symbol."
    elif specific_command == "marketcap":
        return "<b>/marketcap &lt;ticker&gt;</b>\nFetches the current market capitalization of a company."
    elif specific_command == "search":
        return "<b>/search &lt;query&gt;</b>\nSearches the Twelve Data API for a given company name or symbol."

    lines = [
        f"Hello {escaped_name}! I am your Financial Market Bot 📈",
        "",
        "Here are the commands you can use:",
        "📊 <b>/stock &lt;ticker&gt;</b> - Get the current price of a stock",
        "ℹ️ <b>/stockinfo &lt;ticker&gt;</b> - Get detailed company info",
        "📰 <b>/stocknews &lt;ticker&gt;</b> - Get latest news for a stock",
        "💰 <b>/marketcap &lt;ticker&gt;</b> - Get the market cap of a stock",
        "🪙 <b>/crypto &lt;symbol&gt;</b> - Get the current price of a cryptocurrency",
        "📈 <b>/indices</b> - Get current levels of major market indices",
        "🔍 <b>/search &lt;query&gt;</b> - Search for a symbol",
        "",
        "For more info on a command, use <b>/help &lt;command&gt;</b> (e.g., /help stock)",
        "",
        "⚠️ <i>Disclaimer: Data is for informational purposes only, "
        "may be delayed, and does not constitute financial advice.</i>",
    ]
    return "\n".join(lines)


async def setup_commands(application: Application) -> None:
    commands = [
        BotCommand("start", "Show welcome message and help"),
        BotCommand("help", "Show available commands"),
        BotCommand("stock", "Get stock price (e.g., /stock AAPL)"),
        BotCommand("crypto", "Get crypto price (e.g., /crypto BTC)"),
        BotCommand("stockinfo", "Get company info (e.g., /stockinfo AAPL)"),
        BotCommand("stocknews", "Get latest news (e.g., /stocknews AAPL)"),
        BotCommand("marketcap", "Get market cap (e.g., /marketcap AAPL)"),
        BotCommand("indices", "Get major market indices"),
        BotCommand("search", "Search for a symbol (e.g., /search Apple)"),
    ]
    await application.bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
    await application.bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())


async def _ignore_non_command_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/start or /help commanded by {update.effective_user.first_name}")

    specific_command = None
    if context.args:
        specific_command = context.args[0].lower().strip("/")

    help_text = get_help_text(update.effective_user.first_name, specific_command)

    if update.effective_chat.type == ChatType.PRIVATE:
        keyboard = [
            [KeyboardButton("/stock AAPL"), KeyboardButton("/crypto BTC")],
            [KeyboardButton("/indices"), KeyboardButton("/help")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text(help_text, parse_mode="HTML")
