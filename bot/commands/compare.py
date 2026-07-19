import asyncio
import html

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import logger
from bot.services import _get_yfinance_info, format_compact_quote
from bot.symbols import resolve_market_symbol
from bot.utils import DIVIDER, command_guard, send_action


@command_guard
@send_action(ChatAction.TYPING)
async def compare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args or len(context.args) < 2 or len(context.args) > 4:
        await update.message.reply_text(
            "Provide 2–4 tickers. Example: <code>/compare AAPL MSFT</code> or <code>/compare BTC ETH</code>",
            parse_mode="HTML",
        )
        return

    resolved = []
    for raw in context.args:
        result = resolve_market_symbol(raw)
        if result is None:
            await update.message.reply_text(
                f"Invalid ticker: <code>{html.escape(raw)}</code>",
                parse_mode="HTML",
            )
            return
        resolved.append(result)

    try:
        results = await asyncio.gather(
            *[_get_yfinance_info(yf) for yf, _display, _crypto in resolved],
            return_exceptions=True,
        )
        lines = ["⚖️ <b>Compare</b>", DIVIDER]
        for (yf_symbol, display, is_crypto), info in zip(resolved, results):
            if isinstance(info, Exception):
                logger.error(f"Error comparing {yf_symbol}: {info}")
                lines.append(f"<b>{html.escape(display)}</b>: Data unavailable")
            else:
                lines.append(format_compact_quote(info, display, is_crypto=is_crypto))
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in /compare: {e}")
        await update.message.reply_text("Sorry, I couldn't compare those symbols right now.")
