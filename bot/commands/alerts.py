import html

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import logger
from bot.storage import alert_add, alert_list, alert_remove
from bot.symbols import resolve_market_symbol
from bot.utils import DIVIDER, command_guard, send_action


@command_guard
@send_action(ChatAction.TYPING)
async def alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    args = context.args or []

    if not args or args[0].lower() in ("list", "ls"):
        rows = alert_list(chat_id)
        if not rows:
            await update.message.reply_text(
                "No alerts. Create one with <code>/alert add AAPL above 200</code>",
                parse_mode="HTML",
            )
            return
        lines = ["🔔 <b>Alerts</b>", DIVIDER]
        for row in rows:
            lines.append(
                f"<b>#{row['id']}</b> {html.escape(row['symbol'])} {html.escape(row['direction'])} {row['threshold']}"
            )
        lines.append("")
        lines.append("Remove with <code>/alert remove ID</code>")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        return

    action = args[0].lower()

    if action == "add":
        if len(args) < 4:
            await update.message.reply_text(
                "Usage: <code>/alert add AAPL above 200</code> or <code>/alert add BTC above 100000</code>",
                parse_mode="HTML",
            )
            return
        ticker, direction, price_raw = args[1], args[2].lower(), args[3]
        resolved = resolve_market_symbol(ticker)
        if resolved is None:
            await update.message.reply_text("Invalid ticker or crypto symbol format.", parse_mode="HTML")
            return
        yf_symbol, _display, _is_crypto = resolved
        if direction not in ("above", "below"):
            await update.message.reply_text(
                "Direction must be <code>above</code> or <code>below</code>.",
                parse_mode="HTML",
            )
            return
        try:
            threshold = float(price_raw.replace("$", "").replace(",", ""))
        except ValueError:
            await update.message.reply_text("Price must be a number.", parse_mode="HTML")
            return
        ok, msg, _alert_id = alert_add(chat_id, user_id, yf_symbol, direction, threshold)
        prefix = "✅" if ok else "⚠️"
        await update.message.reply_text(f"{prefix} {html.escape(msg)}", parse_mode="HTML")
        return

    if action in ("remove", "rm", "del", "delete"):
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: <code>/alert remove 3</code>",
                parse_mode="HTML",
            )
            return
        try:
            alert_id = int(args[1].lstrip("#"))
        except ValueError:
            await update.message.reply_text("Alert ID must be a number.", parse_mode="HTML")
            return
        ok, msg = alert_remove(chat_id, alert_id)
        prefix = "✅" if ok else "⚠️"
        await update.message.reply_text(f"{prefix} {html.escape(msg)}", parse_mode="HTML")
        return

    await update.message.reply_text(
        "Usage:\n"
        "<code>/alert add AAPL above 200</code>\n"
        "<code>/alert add BTC above 100000</code>\n"
        "<code>/alert list</code>\n"
        "<code>/alert remove 3</code>",
        parse_mode="HTML",
    )
