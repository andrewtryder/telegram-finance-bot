import asyncio
import html

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import INDEX_MAPPING, logger
from bot.services import _get_yfinance_info
from bot.utils import _format_market_time, command_guard, send_action

from .options import get_command_options_text, wants_getopts


def _format_index_value(value) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "N/A"


@command_guard
@send_action(ChatAction.TYPING)
async def indices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get the current levels of major market indices."""
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if wants_getopts(context.args):
        await update.message.reply_text(get_command_options_text("indices"), parse_mode="HTML")
        return

    response_lines = ["📊 <b>Major Market Indices</b>", ""]

    try:
        fetch_tasks = [_get_yfinance_info(symbol) for symbol in INDEX_MAPPING]
        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        for (symbol, readable_name), info in zip(INDEX_MAPPING.items(), results):
            escaped_readable_name = html.escape(readable_name)
            if isinstance(info, Exception):
                logger.error(f"Error fetching index {symbol}: {info}")
                response_lines.append(f"• <b>{escaped_readable_name}</b>: Data unavailable")
                continue

            price = info.get("regularMarketPrice")
            if price is None:
                response_lines.append(f"• <b>{escaped_readable_name}</b>: Data unavailable")
                continue

            change = float(info.get("regularMarketChange") or 0)
            pct_change = float(info.get("regularMarketChangePercent") or 0)
            sign = "+" if change >= 0 else ""
            response_lines.append(
                f"• <b>{escaped_readable_name}</b>: {_format_index_value(price)} "
                f"({sign}{_format_index_value(change)}, {sign}{pct_change:.2f}%)"
            )

            previous_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
            day_low = info.get("regularMarketDayLow") or info.get("dayLow")
            day_high = info.get("regularMarketDayHigh") or info.get("dayHigh")
            details = []
            if previous_close is not None:
                details.append(f"Prev close {_format_index_value(previous_close)}")
            if day_low is not None or day_high is not None:
                details.append(f"Day {_format_index_value(day_low)} - {_format_index_value(day_high)}")
            market_time = _format_market_time(info)
            if market_time:
                details.append(f"As of {market_time}")
            if details:
                response_lines.append(f"   <i>{html.escape(' • '.join(details))}</i>")

    except Exception as e:
        logger.error(f"Error fetching indices: {e}")
        response_lines = ["Sorry, I couldn't fetch the indices right now."]

    await update.message.reply_text("\n".join(response_lines), parse_mode="HTML")
