from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from bot.config import logger
from bot.utils import send_action
from bot.services import get_quote_formatted
from bot.symbols import to_yfinance_crypto, crypto_display_symbol

@send_action(ChatAction.TYPING)
async def crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args:
        await update.message.reply_text("Please provide a crypto symbol. Example: `/crypto BTC`", parse_mode='Markdown')
        return

    symbol = context.args[0]
    yfinance_symbol = to_yfinance_crypto(symbol)
    display_sym = crypto_display_symbol(symbol)

    text = await get_quote_formatted(yfinance_symbol, display_symbol=display_sym)
    await update.message.reply_text(text, parse_mode='Markdown')
