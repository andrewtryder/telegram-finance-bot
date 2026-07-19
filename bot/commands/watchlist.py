import asyncio
import html

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import logger
from bot.services import _get_yfinance_info, format_compact_quote
from bot.storage import watchlist_add, watchlist_list, watchlist_remove
from bot.symbols import to_yfinance_stock, validate_stock_ticker
from bot.utils import DIVIDER, command_guard, send_action


def _require_user_id(update: Update) -> int | None:
    user = update.effective_user
    if user is None or getattr(user, "id", None) is None:
        return None
    return user.id


@command_guard
@send_action(ChatAction.TYPING)
async def watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text if update.message else "/watchlist"
    user_id = _require_user_id(update)
    if user_id is None:
        if update.message:
            await update.message.reply_text(
                "Watchlists are personal and need your Telegram user identity. "
                "If you are posting as an anonymous admin, unhide your identity and try again.",
                parse_mode="HTML",
            )
        return

    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    args = [a.lower() for a in (context.args or [])]

    if not args:
        symbols = watchlist_list(user_id)
        if not symbols:
            await update.message.reply_text(
                "Your watchlist is empty. Add one with <code>/watchlist add AAPL</code>",
                parse_mode="HTML",
            )
            return
        try:
            results = await asyncio.gather(*[_get_yfinance_info(s) for s in symbols], return_exceptions=True)
            lines = ["👀 <b>Your Watchlist</b>", DIVIDER]
            for symbol, info in zip(symbols, results):
                if isinstance(info, Exception):
                    logger.error(f"Watchlist fetch error for {symbol}: {info}")
                    lines.append(f"<b>{html.escape(symbol)}</b>: Data unavailable")
                else:
                    lines.append(format_compact_quote(info, symbol))
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error showing watchlist: {e}")
            await update.message.reply_text("Sorry, I couldn't load your watchlist right now.")
        return

    action = args[0]
    if action in ("add", "remove", "rm", "del", "delete") and len(context.args) < 2:
        await update.message.reply_text(
            f"Usage: <code>/watchlist {action} TICKER</code>",
            parse_mode="HTML",
        )
        return

    if action == "add":
        ticker = context.args[1]
        if not validate_stock_ticker(ticker):
            await update.message.reply_text("Invalid stock ticker format.", parse_mode="HTML")
            return
        ok, msg = watchlist_add(user_id, to_yfinance_stock(ticker))
        prefix = "✅" if ok else "⚠️"
        await update.message.reply_text(f"{prefix} {html.escape(msg)}", parse_mode="HTML")
        return

    if action in ("remove", "rm", "del", "delete"):
        ticker = context.args[1]
        if not validate_stock_ticker(ticker):
            await update.message.reply_text("Invalid stock ticker format.", parse_mode="HTML")
            return
        ok, msg = watchlist_remove(user_id, to_yfinance_stock(ticker))
        prefix = "✅" if ok else "⚠️"
        await update.message.reply_text(f"{prefix} {html.escape(msg)}", parse_mode="HTML")
        return

    await update.message.reply_text(
        "Usage:\n"
        "<code>/watchlist</code> — show quotes\n"
        "<code>/watchlist add AAPL</code>\n"
        "<code>/watchlist remove AAPL</code>",
        parse_mode="HTML",
    )
