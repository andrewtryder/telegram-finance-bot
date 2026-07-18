import asyncio
import logging
import random
import time
from functools import wraps

from cachetools import TTLCache
from telegram import Update
from telegram.ext import ContextTypes

from bot.config import ALLOWED_CHAT_IDS

logger = logging.getLogger(__name__)

# Cooldown state (auto-expires; caps memory for long-running polling)
COOLDOWN_SECONDS = 2.0
USER_COOLDOWNS = TTLCache(maxsize=10_000, ttl=COOLDOWN_SECONDS)


def command_guard(func):
    """
    Decorator to enforce ALLOWED_CHAT_IDS allowlist (if set)
    or lightweight rate limiting (if allowlist is not set).
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        from bot.metrics import record_command

        if not update.effective_chat or not update.effective_user:
            record_command(func.__name__)
            return await func(update, context, *args, **kwargs)

        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        # 1. Enforce allowlist if set (unless 0 is in the allowlist, meaning anyone can talk to the bot)
        if ALLOWED_CHAT_IDS and 0 not in ALLOWED_CHAT_IDS:
            if chat_id not in ALLOWED_CHAT_IDS:
                logger.warning(f"Unauthorized chat attempt: Chat ID {chat_id}")
                if update.message:
                    await update.message.reply_text("Access denied. This bot is private.")
                return
        else:
            # 2. Enforce rate limiting if no allowlist
            now = time.time()
            key = (chat_id, user_id)
            if key in USER_COOLDOWNS:
                last_time = USER_COOLDOWNS[key]
                if now - last_time < COOLDOWN_SECONDS:
                    logger.warning(f"Rate limit hit for User {user_id} in Chat {chat_id}")
                    if update.message:
                        await update.message.reply_text("Too many requests. Please wait a moment.")
                    return
            USER_COOLDOWNS[key] = now

        record_command(func.__name__)
        return await func(update, context, *args, **kwargs)

    return wrapper


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


DIVIDER = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"


def _trend_arrow(change: float) -> str:
    """Returns a directional indicator for a price/level change."""
    if change is None:
        return "▪️"
    if change > 0:
        return "🔺"
    if change < 0:
        return "🔻"
    return "▪️"


def _format_market_time(info: dict) -> str:
    from datetime import datetime, timezone

    epoch = info.get("regularMarketTime")
    if not epoch:
        return ""
    try:
        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception as e:
        logger.error(f"Error formatting time: {e}")
        return ""


def _format_large_number(num: float) -> str:
    if num is None:
        return "N/A"
    try:
        num = float(num)
        if num >= 1_000_000_000_000:
            return f"${num / 1_000_000_000_000:.2f}T"
        elif num >= 1_000_000_000:
            return f"${num / 1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"${num / 1_000_000:.2f}M"
        else:
            return f"${num:,.2f}"
    except (ValueError, TypeError):
        return "N/A"


def _truncate_text(text: str, max_length: int = 400) -> str:
    if not text:
        return "N/A"
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(" ", 1)[0] + "..."


async def execute_provider_call(coro_func, *args, **kwargs):
    """
    Executes a provider-backed function with timeout and retries (with backoff/jitter).
    Attempts: 2 total (1 retry).
    """
    from bot import config

    max_attempts = 2
    last_ex = None

    for attempt in range(max_attempts):
        try:
            return await asyncio.wait_for(coro_func(*args, **kwargs), timeout=config.PROVIDER_TIMEOUT)
        except (asyncio.TimeoutError, Exception) as e:
            last_ex = e
            logger.warning(f"Provider call failed (attempt {attempt + 1}/{max_attempts}): {e}")
            if attempt < max_attempts - 1:
                sleep_time = config.INITIAL_BACKOFF * (2**attempt) + random.uniform(0, 0.1)
                await asyncio.sleep(sleep_time)

    raise last_ex


def validate_url(url: str | None) -> bool:
    if not url:
        return False
    return url.startswith(("http://", "https://"))
