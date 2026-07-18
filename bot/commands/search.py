import html

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import MAX_SEARCH_LEN, TWELVEDATA_API_KEY, logger
from bot.services import fetch_with_cache
from bot.utils import DIVIDER, command_guard, send_action


@command_guard
@send_action(ChatAction.TYPING)
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for a stock, crypto, or ETF symbol."""
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args:
        await update.message.reply_text(
            "Please provide a search term. Example: <code>/search Vanguard</code>",
            parse_mode="HTML",
        )
        return

    query = " ".join(context.args)
    if len(query) > MAX_SEARCH_LEN:
        await update.message.reply_text(
            f"Search query is too long. Maximum length is {MAX_SEARCH_LEN} characters.",
            parse_mode="HTML",
        )
        return

    if not TWELVEDATA_API_KEY:
        await update.message.reply_text("Error: Twelve Data API Key is not configured.")
        return

    url = "https://api.twelvedata.com/symbol_search"
    params = {"symbol": query, "apikey": TWELVEDATA_API_KEY}

    try:
        logger.info(f"Twelve Data search initiated for query: {query}")
        data = await fetch_with_cache(url, params=params)
        logger.debug(f"Raw Search API Response for '{query}': {data}")

        if "data" in data and len(data["data"]) > 0:
            results = data["data"][:5]  # Limit to Top 5 results
            escaped_query = html.escape(query)

            text = f"🔍 <b>Search results for '{escaped_query}'</b>\n{DIVIDER}\n"
            for idx, item in enumerate(results, start=1):
                sym = item.get("symbol", "N/A")
                name = item.get("instrument_name", "N/A")
                exch = item.get("exchange", "N/A")
                type_ = item.get("instrument_type", "N/A")

                escaped_sym = html.escape(sym)
                escaped_name = html.escape(name)
                escaped_exch = html.escape(exch)
                escaped_type = html.escape(type_)
                text += (
                    f"<b>{idx}.</b> <code>{escaped_sym}</code> — {escaped_name} "
                    f"<i>({escaped_exch}, {escaped_type})</i>\n"
                )

            await update.message.reply_text(text, parse_mode="HTML")
        else:
            escaped_query = html.escape(query)
            await update.message.reply_text(f"No results found for '{escaped_query}'.", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error searching for {query}: {e}")
        await update.message.reply_text("Sorry, the search function is currently unavailable.")
