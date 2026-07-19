import html

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import MAX_SEARCH_LEN, logger
from bot.services import search_symbols
from bot.utils import DIVIDER, command_guard, send_action

# Keep results focused on things the bot can actually quote.
_RELEVANT_TYPES = {"EQUITY", "ETF", "CRYPTOCURRENCY", "INDEX", "MUTUALFUND", "CURRENCY"}


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

    escaped_query = html.escape(query)

    try:
        quotes = await search_symbols(query, max_results=8)
        results = [q for q in quotes if q.get("quoteType", "").upper() in _RELEVANT_TYPES][:5]

        if not results:
            await update.message.reply_text(f"No results found for '{escaped_query}'.", parse_mode="HTML")
            return

        text = f"🔍 <b>Search results for '{escaped_query}'</b>\n{DIVIDER}\n"
        for idx, item in enumerate(results, start=1):
            sym = item.get("symbol", "N/A")
            name = item.get("shortname") or item.get("longname") or "N/A"
            exch = item.get("exchDisp") or item.get("exchange") or "N/A"
            type_ = item.get("typeDisp") or item.get("quoteType") or "N/A"

            escaped_sym = html.escape(sym)
            escaped_name = html.escape(name)
            escaped_exch = html.escape(exch)
            escaped_type = html.escape(type_)
            text += (
                f"<b>{idx}.</b> <code>{escaped_sym}</code> — {escaped_name} <i>({escaped_exch}, {escaped_type})</i>\n"
            )

        text += f"\n💡 Try <code>/stock {html.escape(results[0].get('symbol', ''))}</code> for a quote."

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error searching for {query}: {e}")
        await update.message.reply_text("Sorry, the search function is currently unavailable.")
