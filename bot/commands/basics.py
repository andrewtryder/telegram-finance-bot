import html

from telegram import (
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ChatType
from telegram.ext import Application, ContextTypes

from bot.config import logger
from bot.utils import DIVIDER


def get_help_text(first_name: str = "there", specific_command: str = None) -> str:
    escaped_name = html.escape(first_name)

    if specific_command == "stock":
        return (
            f"<b>/stock &lt;ticker&gt;</b>\n{DIVIDER}\n"
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
            f"<b>/crypto &lt;symbol&gt;</b>\n{DIVIDER}\n"
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
            f"<b>/indices</b>\n{DIVIDER}\n"
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
        f"👋 Hello {escaped_name}! I am your Financial Market Bot 📈",
        DIVIDER,
        "",
        "📈 <b>Stocks</b>",
        "📊 <b>/stock &lt;ticker&gt;</b> - Current price of a stock",
        "ℹ️ <b>/stockinfo &lt;ticker&gt;</b> - Detailed company info",
        "📰 <b>/stocknews &lt;ticker&gt;</b> - Latest news for a stock",
        "💰 <b>/marketcap &lt;ticker&gt;</b> - Market cap of a stock",
        "",
        "🪙 <b>Crypto &amp; Markets</b>",
        "🪙 <b>/crypto &lt;symbol&gt;</b> - Current price of a cryptocurrency",
        "📈 <b>/indices</b> - Levels of major market indices",
        "",
        "🔍 <b>Search</b>",
        "🔍 <b>/search &lt;query&gt;</b> - Search for a symbol",
        "",
        DIVIDER,
        "💡 For more info on a command, use <b>/help &lt;command&gt;</b> (e.g., <code>/help stock</code>)",
        "",
        "⚠️ <i>Disclaimer: Data is for informational purposes only, "
        "may be delayed, and does not constitute financial advice.</i>",
    ]
    return "\n".join(lines)


async def setup_commands(application: Application) -> None:
    await application.bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
    await application.bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
    await application.bot.delete_my_commands()


async def _ignore_non_command_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/start or /help commanded by {update.effective_user.first_name}")

    specific_command = None
    if context.args:
        specific_command = context.args[0].lower().strip("/")

    help_text = get_help_text(update.effective_user.first_name, specific_command)

    if update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text(help_text, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")
    else:
        await update.message.reply_text(help_text, parse_mode="HTML")
