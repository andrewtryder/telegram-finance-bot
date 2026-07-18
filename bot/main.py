from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.commands import (
    _ignore_non_command_group_messages,
    crypto,
    indices,
    marketcap,
    search,
    setup_commands,
    start,
    stock,
    stockinfo,
    stocknews,
)
from bot.config import TELEGRAM_BOT_TOKEN, init_honeybadger, logger, notify_honeybadger
from bot.services import close_http_client, init_http_client

# Optional: Only ignore text/commands in groups if you didn't enable Privacy Mode
GROUP_PRIVACY_FILTER = filters.ChatType.GROUPS & ~filters.COMMAND & ~filters.Regex(r"^/")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unexpected exceptions and reply with a generic safe message."""
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

    if isinstance(update, Update) and update.message:
        try:
            await update.message.reply_text("An unexpected error occurred. Please try again later.")
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")


async def post_init(application) -> None:
    await setup_commands(application)
    await init_http_client()


async def post_shutdown(application) -> None:
    await close_http_client()


def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in the environment variables.")
        return

    init_honeybadger()

    application = (
        ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    )

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("stock", stock))
    application.add_handler(CommandHandler("crypto", crypto))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("stockinfo", stockinfo))
    application.add_handler(CommandHandler("stocknews", stocknews))
    application.add_handler(CommandHandler("marketcap", marketcap))

    # Passing a tuple lets one function handle multiple spellings of the command!
    application.add_handler(CommandHandler(("indices", "indicies"), indices))

    # Error handler
    application.add_error_handler(error_handler)

    # Groups: only respond to /commands (matches BotFather privacy mode behavior).
    application.add_handler(
        MessageHandler(GROUP_PRIVACY_FILTER, _ignore_non_command_group_messages),
        group=1,
    )

    logger.info("Starting bot... Waiting for commands.")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
