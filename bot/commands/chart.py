import html

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import logger
from bot.services import get_history_chart_png
from bot.symbols import to_yfinance_stock, validate_stock_ticker
from bot.utils import command_guard, send_action

ALLOWED_PERIODS = {"1mo", "3mo", "6mo", "1y"}


@command_guard
@send_action(ChatAction.UPLOAD_PHOTO)
async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/chart AAPL</code> or <code>/chart AAPL 3mo</code> (1mo, 3mo, 6mo, 1y)",
            parse_mode="HTML",
        )
        return

    ticker = context.args[0]
    period = context.args[1].lower() if len(context.args) > 1 else "1mo"
    if period not in ALLOWED_PERIODS:
        await update.message.reply_text(
            "Period must be one of: <code>1mo</code>, <code>3mo</code>, <code>6mo</code>, <code>1y</code>",
            parse_mode="HTML",
        )
        return

    if not validate_stock_ticker(ticker):
        await update.message.reply_text("Invalid stock ticker format.", parse_mode="HTML")
        return

    yfinance_symbol = to_yfinance_stock(ticker)
    try:
        png = await get_history_chart_png(yfinance_symbol, period=period)
        if not png:
            await update.message.reply_text(
                f"Could not build a chart for {html.escape(yfinance_symbol)}.",
                parse_mode="HTML",
            )
            return
        await update.message.reply_photo(
            photo=png,
            caption=f"📈 {yfinance_symbol} · {period}",
        )
    except Exception as e:
        logger.error(f"Error in /chart for {yfinance_symbol}: {e}")
        await update.message.reply_text("Sorry, I couldn't generate that chart right now.")
