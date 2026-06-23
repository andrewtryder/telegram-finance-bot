from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram import BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, BotCommand
from telegram.ext import ContextTypes, Application
from telegram.constants import ChatType
from bot.config import logger

def get_help_text(first_name: str = "there") -> str:
    lines = [
        f"Hello {first_name}! I am your Financial Market Bot 📈",
        "",
        "Here are the commands you can use:",
        "🔹 /stock <ticker> - Get the current price of a stock",
        "🔹 /stockinfo <ticker> - Get detailed company info",
        "🔹 /stocknews <ticker> - Get latest news for a stock",
        "🔹 /marketcap <ticker> - Get the market cap of a stock",
        "🔹 /crypto <symbol> - Get the current price of a cryptocurrency",
        "🔹 /indices - Get current levels of major market indices",
        "🔹 /search <query> - Search for a symbol",
        "",
        "Examples: /stock AAPL, /crypto BTC"
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

async def _ignore_non_command_group_messages(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/start or /help commanded by {update.effective_user.first_name}")
    help_text = get_help_text(update.effective_user.first_name)

    if update.effective_chat.type == ChatType.PRIVATE:
        keyboard = [
            [KeyboardButton("/stock AAPL"), KeyboardButton("/crypto BTC")],
            [KeyboardButton("/indices"), KeyboardButton("/help")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(help_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(help_text)
