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


def get_help_text(first_name: str = "there") -> str:
    escaped_name = html.escape(first_name)
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
        "Examples: /stock AAPL, /crypto BTC",
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
    help_text = get_help_text(update.effective_user.first_name)

    if update.effective_chat.type == ChatType.PRIVATE:
        keyboard = [
            [KeyboardButton("/stock AAPL"), KeyboardButton("/crypto BTC")],
            [KeyboardButton("/indices"), KeyboardButton("/help")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text(help_text, parse_mode="HTML")
