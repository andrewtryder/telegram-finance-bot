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

from .options import get_all_commands_help_text


def get_help_text(first_name: str = "there") -> str:
    return get_all_commands_help_text(first_name)


async def setup_commands(application: Application) -> None:
    commands = [
        BotCommand("start", "Show welcome message and help"),
        BotCommand("help", "Show commands, examples, and options"),
        BotCommand("stock", "Get a detailed stock quote"),
        BotCommand("crypto", "Get a detailed crypto quote"),
        BotCommand("stockinfo", "Get company profile and fundamentals"),
        BotCommand("stocknews", "Get recent stock news"),
        BotCommand("marketcap", "Get valuation details"),
        BotCommand("indices", "Get major market indices"),
        BotCommand("search", "Search for a market symbol"),
    ]
    await application.bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
    await application.bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())


async def _ignore_non_command_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


async def _reply_with_help(update: Update, first_name: str) -> None:
    help_text = get_help_text(first_name)

    if update.effective_chat.type == ChatType.PRIVATE:
        keyboard = [
            [KeyboardButton("/stock AAPL"), KeyboardButton("/crypto BTC")],
            [KeyboardButton("/indices"), KeyboardButton("/stock --getopts")],
            [KeyboardButton("/search Apple"), KeyboardButton("/help")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text(help_text, parse_mode="HTML")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    first_name = update.effective_user.first_name if update.effective_user else "there"
    logger.info(f"/start commanded by {first_name}")
    await _reply_with_help(update, first_name)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    first_name = update.effective_user.first_name if update.effective_user else "there"
    logger.info(f"/help commanded by {first_name}")
    await _reply_with_help(update, first_name)
