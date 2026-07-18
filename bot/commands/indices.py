import asyncio
import html

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import INDEX_MAPPING, logger
from bot.services import _format_price, _get_yfinance_info
from bot.utils import DIVIDER, _trend_arrow, command_guard, send_action


@command_guard
@send_action(ChatAction.TYPING)
async def indices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get the current levels of major market indices."""
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    blocks = [f"📊 <b>Major Market Indices</b>\n{DIVIDER}"]

    try:
        fetch_tasks = [_get_yfinance_info(symbol) for symbol in INDEX_MAPPING]
        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        for (symbol, readable_name), info in zip(INDEX_MAPPING.items(), results):
            escaped_readable_name = html.escape(readable_name)
            if isinstance(info, Exception):
                logger.error(f"Error fetching index {symbol}: {info}")
                blocks.append(f"🔸 <b>{escaped_readable_name}</b>\nData unavailable")
                continue

            price = info.get("lastPrice") or info.get("regularMarketPrice") or info.get("currentPrice")
            if price is None:
                blocks.append(f"🔸 <b>{escaped_readable_name}</b>\nData unavailable")
                continue

            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")

            if prev_close is not None and prev_close != 0:
                change = price - prev_close
                change_pct = (change / prev_close) * 100
            else:
                change = info.get("regularMarketChange", 0.0)
                change_pct = info.get("regularMarketChangePercent", 0.0)

            sign = "+" if change >= 0 else ""
            arrow = _trend_arrow(change)

            line = (
                f"🔸 <b>{escaped_readable_name}:</b> {_format_price(price, False)}  "
                f"{arrow} {sign}{change:,.2f} ({sign}{change_pct:.2f}%)"
            )

            # Add ranges if we have them, kept compact as one trailing clause
            range_bits = []
            day_high = info.get("dayHigh") or info.get("regularMarketDayHigh")
            day_low = info.get("dayLow") or info.get("regularMarketDayLow")
            if day_high is not None and day_low is not None:
                range_bits.append(f"Day {day_low:,.2f}–{day_high:,.2f}")

            week_high = info.get("weekHigh")
            week_low = info.get("weekLow")
            if week_high is not None and week_low is not None:
                range_bits.append(f"Week {week_low:,.2f}–{week_high:,.2f}")

            year_high = info.get("yearHigh") or info.get("fiftyTwoWeekHigh")
            year_low = info.get("yearLow") or info.get("fiftyTwoWeekLow")
            if year_high is not None and year_low is not None:
                range_bits.append(f"52W {year_low:,.2f}–{year_high:,.2f}")

            if range_bits:
                line += f"\n<i>{' · '.join(range_bits)}</i>"

            blocks.append(line)

        response_text = f"\n{DIVIDER}\n".join(blocks)

    except Exception as e:
        logger.error(f"Error fetching indices: {e}")
        response_text = "Sorry, I couldn't fetch the indices right now."

    await update.message.reply_text(response_text, parse_mode="HTML")
