from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import logger
from bot.services import get_quote_formatted
from bot.symbols import (
    crypto_display_symbol,
    to_yfinance_crypto,
    validate_crypto_symbol,
)
from bot.utils import command_guard, send_action


@command_guard
@send_action(ChatAction.TYPING)
async def crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args:
        await update.message.reply_text(
            "Please provide a crypto symbol. Example: <code>/crypto BTC</code>",
            parse_mode="HTML",
        )
        return

    symbol = context.args[0]
    if not validate_crypto_symbol(symbol):
        await update.message.reply_text(
            "Invalid crypto symbol format. Example: <code>BTC</code>, <code>BTC/USD</code>, or <code>ETH-USD</code>.",
            parse_mode="HTML",
        )
        return

    yfinance_symbol = to_yfinance_crypto(symbol)
    display_sym = crypto_display_symbol(symbol)

    text = await get_quote_formatted(yfinance_symbol, display_symbol=display_sym)
    await update.message.reply_text(text, parse_mode="HTML")
