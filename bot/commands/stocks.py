from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
import asyncio

from bot.config import logger
from bot.utils import send_action, _format_large_number, _truncate_text
from bot.services import get_quote_formatted, _get_yfinance_info, _fetch_yfinance_news
from bot.symbols import to_yfinance_stock

@send_action(ChatAction.TYPING)
async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args:
        await update.message.reply_text("Please provide a stock ticker. Example: `/stock AAPL`", parse_mode='Markdown')
        return

    ticker = context.args[0]
    yfinance_symbol = to_yfinance_stock(ticker)

    text = await get_quote_formatted(yfinance_symbol, display_symbol=ticker.upper())
    await update.message.reply_text(text, parse_mode='Markdown')

@send_action(ChatAction.TYPING)
async def stockinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args:
        await update.message.reply_text("Please provide a stock ticker. Example: `/stockinfo AAPL`", parse_mode='Markdown')
        return

    ticker = context.args[0]
    yfinance_symbol = to_yfinance_stock(ticker)

    try:
        info = await _get_yfinance_info(yfinance_symbol)

        name = info.get("shortName") or info.get("longName") or yfinance_symbol
        sector = info.get("sector", "N/A")
        industry = info.get("industry", "N/A")
        market_cap = _format_large_number(info.get("marketCap"))
        pe_ratio = info.get("trailingPE") or info.get("forwardPE")
        pe_str = f"{pe_ratio:.2f}" if isinstance(pe_ratio, (int, float)) else "N/A"

        div_yield = info.get("dividendYield")
        div_str = f"{div_yield * 100:.2f}%" if isinstance(div_yield, (int, float)) else "N/A"

        high52 = info.get("fiftyTwoWeekHigh")
        high52_str = f"${high52:,.2f}" if isinstance(high52, (int, float)) else "N/A"

        low52 = info.get("fiftyTwoWeekLow")
        low52_str = f"${low52:,.2f}" if isinstance(low52, (int, float)) else "N/A"

        summary = _truncate_text(info.get("longBusinessSummary", "No summary available."))

        lines = [
            f"ℹ️ **{name} ({yfinance_symbol})**",
            f"**Sector:** {sector}",
            f"**Industry:** {industry}",
            "",
            f"**Market Cap:** {market_cap}",
            f"**P/E Ratio:** {pe_str}",
            f"**Dividend Yield:** {div_str}",
            f"**52W High/Low:** {high52_str} / {low52_str}",
            "",
            f"**Summary:** {summary}"
        ]

        await update.message.reply_text("\n".join(lines), parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error fetching info for {yfinance_symbol}: {e}")
        await update.message.reply_text("Sorry, I couldn't fetch info for that symbol right now.")

@send_action(ChatAction.TYPING)
async def stocknews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args:
        await update.message.reply_text("Please provide a stock ticker. Example: `/stocknews AAPL`", parse_mode='Markdown')
        return

    ticker = context.args[0]
    yfinance_symbol = to_yfinance_stock(ticker)

    try:
        news_items = await asyncio.to_thread(_fetch_yfinance_news, yfinance_symbol)
        if not news_items:
            await update.message.reply_text(f"No recent news found for {yfinance_symbol}.")
            return

        lines = [f"📰 **Recent news for {yfinance_symbol}**", ""]
        for item in news_items[:5]:
            content = item.get('content', {}) if 'content' in item else item
            title = content.get('title', 'No Title')

            url = ""
            if 'clickThroughUrl' in content:
                url = content['clickThroughUrl'].get('url', '')
            elif 'link' in item:
                url = item['link']

            lines.append(f"• [{title}]({url})")

        await update.message.reply_text("\n".join(lines), parse_mode='Markdown', disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error fetching news for {yfinance_symbol}: {e}")
        await update.message.reply_text("Sorry, I couldn't fetch news for that symbol right now.")

@send_action(ChatAction.TYPING)
async def marketcap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args:
        await update.message.reply_text("Please provide a stock ticker. Example: `/marketcap AAPL`", parse_mode='Markdown')
        return

    ticker = context.args[0]
    yfinance_symbol = to_yfinance_stock(ticker)

    try:
        info = await _get_yfinance_info(yfinance_symbol)

        name = info.get("shortName") or info.get("longName") or yfinance_symbol
        market_cap = _format_large_number(info.get("marketCap"))

        text = f"💰 **{name} ({yfinance_symbol})** Market Cap: {market_cap}"
        await update.message.reply_text(text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error fetching market cap for {yfinance_symbol}: {e}")
        await update.message.reply_text("Sorry, I couldn't fetch data for that symbol right now.")
