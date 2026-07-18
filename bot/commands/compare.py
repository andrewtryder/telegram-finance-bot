import asyncio
import html

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import logger
from bot.services import _get_yfinance_info, format_compact_quote
from bot.symbols import to_yfinance_stock, validate_stock_ticker
from bot.utils import DIVIDER, command_guard, send_action


@command_guard
@send_action(ChatAction.TYPING)
async def compare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args or len(context.args) < 2 or len(context.args) > 4:
        await update.message.reply_text(
            "Provide 2–4 tickers. Example: <code>/compare AAPL MSFT</code>",
            parse_mode="HTML",
        )
        return

    tickers = []
    for raw in context.args:
        if not validate_stock_ticker(raw):
            await update.message.reply_text(
                f"Invalid ticker: <code>{html.escape(raw)}</code>",
                parse_mode="HTML",
            )
            return
        tickers.append(to_yfinance_stock(raw))

    try:
        results = await asyncio.gather(*[_get_yfinance_info(t) for t in tickers], return_exceptions=True)
        lines = ["⚖️ <b>Compare</b>", DIVIDER]
        for ticker, info in zip(tickers, results):
            if isinstance(info, Exception):
                logger.error(f"Error comparing {ticker}: {info}")
                lines.append(f"<b>{html.escape(ticker)}</b>: Data unavailable")
            else:
                lines.append(format_compact_quote(info, ticker))
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in /compare: {e}")
        await update.message.reply_text("Sorry, I couldn't compare those symbols right now.")
