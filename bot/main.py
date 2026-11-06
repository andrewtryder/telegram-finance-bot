from telegram import Update
from telegram.error import Conflict
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.commands import (
    _ignore_non_command_group_messages,
    admin,
    chart,
    compare,
    crypto,
    indices,
    marketcap,
    retired_command,
    search,
    setup_commands,
    start,
    stock,
    stockinfo,
    stocknews,
)
from bot.config import (
    BOT_MODE,
    DROP_PENDING_UPDATES,
    TELEGRAM_BOT_TOKEN,
    init_honeybadger,
    is_network_timeout,
    logger,
    notify_honeybadger,
    validate_config,
)
from bot.metrics import record_error, snapshot

# Optional: Only ignore text/commands in groups if you didn't enable Privacy Mode
GROUP_PRIVACY_FILTER = filters.ChatType.GROUPS & ~filters.COMMAND & ~filters.Regex(r"^/")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unexpected exceptions and reply with a generic safe message."""
    # Another process is long-polling the same token; not actionable as an app bug.
    if isinstance(context.error, Conflict):
        logger.warning(
            "Telegram Conflict: another getUpdates poller is using this bot token. "
            "Ensure only one instance is running (e.g. stop local bots while Railway is up, "
            "and keep Railway replicas at 1)."
        )
        return

    # Transient network timeouts are normal during long-polling / network requests.
    if is_network_timeout(context.error):
        logger.warning(f"Telegram network timeout encountered: {context.error}")
        return

    record_error()
    logger.exception("Exception occurred while handling an update:", exc_info=context.error)

    hb_context = {}
    if isinstance(update, Update):
        if update.effective_chat:
            hb_context["chat_id"] = update.effective_chat.id
            hb_context["chat_type"] = update.effective_chat.type
        if update.effective_user:
            hb_context["user_id"] = update.effective_user.id
        if update.effective_message and update.effective_message.text:
            hb_context["message_text"] = update.effective_message.text[:200]

    notify_honeybadger(context.error, **hb_context)

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("An unexpected error occurred. Please try again later.")
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")


async def post_init(application) -> None:
    webhook = await application.bot.get_webhook_info()
    if webhook.url:
        raise RuntimeError("Telegram webhook is active; remove it before starting polling")
    await setup_commands(application)


async def post_shutdown(application) -> None:
    data = snapshot()
    logger.info(f"metrics_snapshot_shutdown {data}")


def register_handlers(application):
    """Register the command and error handlers for any transport."""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("stock", stock))
    application.add_handler(CommandHandler("crypto", crypto))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("stockinfo", stockinfo))
    application.add_handler(CommandHandler("stocknews", stocknews))
    application.add_handler(CommandHandler("marketcap", marketcap))
    application.add_handler(CommandHandler("compare", compare))
    application.add_handler(CommandHandler("chart", chart))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler(("indices", "indicies"), indices))

    # Gracefully inform users when retired stateful commands are sent
    application.add_handler(CommandHandler(("alert", "watchlist"), retired_command))

    # Error handler
    application.add_error_handler(error_handler)

    # Groups: only respond to /commands (matches BotFather privacy mode behavior).
    application.add_handler(
        MessageHandler(GROUP_PRIVACY_FILTER, _ignore_non_command_group_messages),
        group=1,
    )


def main():
    """Start the bot in polling mode."""
    validate_config()
    if BOT_MODE != "polling":
        raise RuntimeError("bot.main only supports polling mode")
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in the environment variables.")
        return

    init_honeybadger()

    application = (
        ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    )
    register_handlers(application)

    logger.info(f"Starting bot (drop_pending_updates={DROP_PENDING_UPDATES})... Waiting for commands.")
    application.run_polling(drop_pending_updates=DROP_PENDING_UPDATES)


if __name__ == "__main__":
    main()
