from urllib.parse import quote
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction, ParseMode
from telegram.helpers import escape_markdown

from bot.config import logger, TWELVEDATA_API_KEY
from bot.utils import send_action
from bot.services import fetch_with_cache

@send_action(ChatAction.TYPING)
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for a stock, crypto, or ETF symbol."""
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args:
        await update.message.reply_text("Please provide a search term. Example: `/search Vanguard`", parse_mode='Markdown')
        return

    if not TWELVEDATA_API_KEY:
        await update.message.reply_text("Error: Twelve Data API Key is not configured.")
        return

    query = " ".join(context.args)
    encoded_query = quote(query)
    url = f"https://api.twelvedata.com/symbol_search?symbol={encoded_query}&apikey={TWELVEDATA_API_KEY}"

    try:
        data = await fetch_with_cache(url)

        # Debug logging
        logger.info(f"Raw Search API Response for '{query}': {data}")

        if "data" in data and len(data["data"]) > 0:
            results = data["data"][:5] # Limit to Top 5 results
            escaped_query = escape_markdown(query, version=2)

            lines = [
                f"• *{escape_markdown(item.get('symbol', 'N/A'), version=2)}* \\- "
                f"{escape_markdown(item.get('instrument_name', 'N/A'), version=2)} "
                f"\\({escape_markdown(item.get('exchange', 'N/A'), version=2)}, "
                f"{escape_markdown(item.get('instrument_type', 'N/A'), version=2)}\\)"
                for item in results
            ]
            text = f"🔍 *Search results for '{escaped_query}':*\n\n" + "\n".join(lines) + "\n"

            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            escaped_query = escape_markdown(query, version=2)
            await update.message.reply_text(f"No results found for '{escaped_query}'\\.", parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        logger.error(f"Error searching for {query}: {e}")
        await update.message.reply_text("Sorry, the search function is currently unavailable.")
