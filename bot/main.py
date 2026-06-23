from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)
from bot.config import logger, TELEGRAM_BOT_TOKEN
from bot.commands import (
    start,
    setup_commands,
    _ignore_non_command_group_messages,
    stock,
    stockinfo,
    stocknews,
    marketcap,
    crypto,
    indices,
    search,
)

# Optional: Only ignore text/commands in groups if you didn't enable Privacy Mode
GROUP_PRIVACY_FILTER = filters.ChatType.GROUPS & ~filters.COMMAND & ~filters.Regex(r'^/')

def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in the environment variables.")
        return

    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(setup_commands)
        .build()
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

    # Groups: only respond to /commands (matches BotFather privacy mode behavior).
    application.add_handler(
        MessageHandler(GROUP_PRIVACY_FILTER, _ignore_non_command_group_messages),
        group=1,
    )

    logger.info("Starting bot... Waiting for commands.")
    application.run_polling()

if __name__ == '__main__':
    main()
