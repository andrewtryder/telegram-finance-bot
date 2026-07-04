import asyncio
import html

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import INDEX_MAPPING, logger
from bot.services import _get_yfinance_info
from bot.utils import command_guard, send_action


@command_guard
@send_action(ChatAction.TYPING)
async def indices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get the current levels of major market indices."""
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    response_text = "📊 <b>Major Market Indices</b>\n\n"

    try:
        fetch_tasks = [_get_yfinance_info(symbol) for symbol in INDEX_MAPPING]
        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        for (symbol, readable_name), info in zip(INDEX_MAPPING.items(), results):
            escaped_readable_name = html.escape(readable_name)
            if isinstance(info, Exception):
                logger.error(f"Error fetching index {symbol}: {info}")
                response_text += f"• <b>{escaped_readable_name}</b>: Data unavailable\n"
                continue

            price = info.get("regularMarketPrice")
            if price is None:
                response_text += f"• <b>{escaped_readable_name}</b>: Data unavailable\n"
                continue

            pct_change = float(info.get("regularMarketChangePercent") or 0)
            sign = "+" if pct_change >= 0 else ""
            response_text += f"• <b>{escaped_readable_name}</b>: {price:,.2f} ({sign}{pct_change:.2f}%)\n"

    except Exception as e:
        logger.error(f"Error fetching indices: {e}")
        response_text = "Sorry, I couldn't fetch the indices right now."

    await update.message.reply_text(response_text, parse_mode="HTML")
