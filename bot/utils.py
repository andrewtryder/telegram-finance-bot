from functools import wraps
from telegram.constants import ChatAction
import logging

logger = logging.getLogger(__name__)

def send_action(action):
    """Sends `action` while processing func command."""
    def decorator(func):
        @wraps(func)
        async def command_func(update, context, *args, **kwargs):
            if update.message:
                await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=action)
            return await func(update, context, *args, **kwargs)
        return command_func
    return decorator

def _format_market_time(info: dict) -> str:
    from datetime import datetime, timezone
    epoch = info.get("regularMarketTime")
    if not epoch:
        return ""
    try:
        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except Exception as e:
        logger.error(f"Error formatting time: {e}")
        return ""

def _format_large_number(num: float) -> str:
    if num is None:
        return "N/A"
    try:
        num = float(num)
        if num >= 1_000_000_000_000:
            return f"${num/1_000_000_000_000:.2f}T"
        elif num >= 1_000_000_000:
            return f"${num/1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"${num/1_000_000:.2f}M"
        else:
            return f"${num:,.2f}"
    except (ValueError, TypeError):
        return "N/A"

def _truncate_text(text: str, max_length: int = 400) -> str:
    if not text:
        return "N/A"
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(' ', 1)[0] + "..."
