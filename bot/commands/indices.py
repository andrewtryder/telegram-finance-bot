from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
import asyncio

from bot.config import logger, INDEX_MAPPING
from bot.utils import send_action
from bot.services import _get_yfinance_info

@send_action(ChatAction.TYPING)
async def indices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get the current levels of major market indices."""
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

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
