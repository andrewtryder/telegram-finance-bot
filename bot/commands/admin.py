from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import ADMIN_USER_IDS, logger
from bot.metrics import format_stats_html
from bot.utils import command_guard, send_action


def _is_admin(user_id: int | None) -> bool:
    return bool(ADMIN_USER_IDS) and user_id is not None and user_id in ADMIN_USER_IDS


@command_guard
@send_action(ChatAction.TYPING)
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text if update.message else "/admin"
    user = update.effective_user
    logger.info(f"Command received: {command_text} from {user.first_name if user else 'unknown'}")

    if not _is_admin(user.id if user else None):
        if update.message:
            await update.message.reply_text("Access denied.", parse_mode="HTML")
        return

    args = [a.lower() for a in (context.args or [])]
    action = args[0] if args else "stats"

    if action in ("stats", "status", "metrics"):
        await update.message.reply_text(format_stats_html(), parse_mode="HTML")
        return

    await update.message.reply_text(
        "Usage: <code>/admin stats</code>",
        parse_mode="HTML",
    )
