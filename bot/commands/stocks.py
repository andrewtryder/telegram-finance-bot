import html

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.config import logger
from bot.services import (
    _get_yfinance_info,
    _get_yfinance_news,
    get_quote_formatted,
)
from bot.symbols import to_yfinance_stock, validate_stock_ticker
from bot.utils import (
    _format_large_number,
    _truncate_text,
    command_guard,
    send_action,
    validate_url,
)


@command_guard
@send_action(ChatAction.TYPING)
async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args:
        await update.message.reply_text(
            "Please provide a stock ticker. Example: <code>/stock AAPL</code>",
            parse_mode="HTML",
        )
        return

    ticker = context.args[0]
    if not validate_stock_ticker(ticker):
        await update.message.reply_text(
            "Invalid stock ticker format. Tickers must be up to 16 alphanumeric "
            "characters, dots, dashes, equal signs, or carets.",
            parse_mode="HTML",
        )
        return

    yfinance_symbol = to_yfinance_stock(ticker)

    text = await get_quote_formatted(yfinance_symbol, display_symbol=ticker.upper(), is_crypto=False)
    await update.message.reply_text(text, parse_mode="HTML")


@command_guard
@send_action(ChatAction.TYPING)
async def stockinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args:
        await update.message.reply_text(
            "Please provide a stock ticker. Example: <code>/stockinfo AAPL</code>",
            parse_mode="HTML",
        )
        return

    ticker = context.args[0]
    if not validate_stock_ticker(ticker):
        await update.message.reply_text(
            "Invalid stock ticker format. Tickers must be up to 16 alphanumeric "
            "characters, dots, dashes, equal signs, or carets.",
            parse_mode="HTML",
        )
        return

    yfinance_symbol = to_yfinance_stock(ticker)

    try:
        info = await _get_yfinance_info(yfinance_symbol)
        if not info or not (info.get("longName") or info.get("shortName")):
            await update.message.reply_text(
                f"Could not find company info for {html.escape(yfinance_symbol)}.",
                parse_mode="HTML",
            )
            return

        name = info.get("shortName") or info.get("longName") or yfinance_symbol
        sector = info.get("sector", "N/A")
        industry = info.get("industry", "N/A")
        market_cap = _format_large_number(info.get("marketCap"))
        pe_ratio = info.get("trailingPE") or info.get("forwardPE")
        pe_str = f"{pe_ratio:.2f}" if isinstance(pe_ratio, (int, float)) else "N/A"

        div_yield = info.get("dividendYield")
        div_str = f"{div_yield * 100:.2f}%" if isinstance(div_yield, (int, float)) else "N/A"

        high52 = info.get("yearHigh") or info.get("fiftyTwoWeekHigh")
        high52_str = f"${high52:,.2f}" if isinstance(high52, (int, float)) else "N/A"

        low52 = info.get("yearLow") or info.get("fiftyTwoWeekLow")
        low52_str = f"${low52:,.2f}" if isinstance(low52, (int, float)) else "N/A"

        summary = _truncate_text(info.get("longBusinessSummary") or info.get("description") or "No summary available.")
        website = info.get("website")

        escaped_name = html.escape(name)
        escaped_symbol = html.escape(yfinance_symbol)
        escaped_sector = html.escape(sector)
        escaped_industry = html.escape(industry)
        escaped_summary = html.escape(summary)

        lines = [
            f"ℹ️ <b>{escaped_name} ({escaped_symbol})</b>",
            f"<b>Sector:</b> {escaped_sector}",
            f"<b>Industry:</b> {escaped_industry}",
            "",
            f"<b>Market Cap:</b> {html.escape(market_cap)}",
            f"<b>P/E Ratio:</b> {html.escape(pe_str)}",
            f"<b>Dividend Yield:</b> {html.escape(div_str)}",
            f"<b>52W High/Low:</b> {html.escape(high52_str)} / {html.escape(low52_str)}",
        ]

        if website:
            if validate_url(website):
                escaped_website = html.escape(website)
                lines.append(f'<b>Website:</b> <a href="{escaped_website}">{escaped_website}</a>')
            else:
                lines.append(f"<b>Website:</b> {html.escape(website)}")

        lines.extend(["", f"<b>Summary:</b> <i>{escaped_summary}</i>"])

        await update.message.reply_text("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error fetching info for {yfinance_symbol}: {e}")
        await update.message.reply_text("Sorry, I couldn't fetch info for that symbol right now.")


@command_guard
@send_action(ChatAction.TYPING)
async def stocknews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args:
        await update.message.reply_text(
            "Please provide a stock ticker. Example: <code>/stocknews AAPL</code>",
            parse_mode="HTML",
        )
        return

    ticker = context.args[0]
    if not validate_stock_ticker(ticker):
        await update.message.reply_text(
            "Invalid stock ticker format. Tickers must be up to 16 alphanumeric "
            "characters, dots, dashes, equal signs, or carets.",
            parse_mode="HTML",
        )
        return

    yfinance_symbol = to_yfinance_stock(ticker)

    try:
        news_items = await _get_yfinance_news(yfinance_symbol)
        if not news_items:
            await update.message.reply_text(
                f"No recent news found for {html.escape(yfinance_symbol)}.",
                parse_mode="HTML",
            )
            return

        lines = [f"📰 <b>Recent news for {html.escape(yfinance_symbol)}</b>", ""]
        for item in news_items[:5]:
            content = item.get("content", {}) if "content" in item else item
            title = content.get("title", "No Title")

            url = ""
            if "clickThroughUrl" in content:
                url = content["clickThroughUrl"].get("url", "")
            elif "link" in item:
                url = item["link"]

            escaped_title = html.escape(title)
            if validate_url(url):
                escaped_url = html.escape(url)
                lines.append(f'• <a href="{escaped_url}">{escaped_title}</a>')
            else:
                lines.append(f"• {escaped_title}")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error fetching news for {yfinance_symbol}: {e}")
        await update.message.reply_text("Sorry, I couldn't fetch news for that symbol right now.")


@command_guard
@send_action(ChatAction.TYPING)
async def marketcap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if not context.args:
        await update.message.reply_text(
            "Please provide a stock ticker. Example: <code>/marketcap AAPL</code>",
            parse_mode="HTML",
        )
        return

    ticker = context.args[0]
    if not validate_stock_ticker(ticker):
        await update.message.reply_text(
            "Invalid stock ticker format. Tickers must be up to 16 alphanumeric "
            "characters, dots, dashes, equal signs, or carets.",
            parse_mode="HTML",
        )
        return

    yfinance_symbol = to_yfinance_stock(ticker)

    try:
        info = await _get_yfinance_info(yfinance_symbol)
        if not info or not (info.get("longName") or info.get("shortName")):
            await update.message.reply_text(
                f"Could not find company info for {html.escape(yfinance_symbol)}.",
                parse_mode="HTML",
            )
            return

        name = info.get("shortName") or info.get("longName") or yfinance_symbol
        market_cap = _format_large_number(info.get("marketCap"))

        escaped_name = html.escape(name)
        escaped_symbol = html.escape(yfinance_symbol)
        escaped_cap = html.escape(market_cap)

        text = f"💰 <b>{escaped_name} ({escaped_symbol})</b> Market Cap: <b>{escaped_cap}</b>"
        await update.message.reply_text(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error fetching market cap for {yfinance_symbol}: {e}")
        await update.message.reply_text("Sorry, I couldn't fetch data for that symbol right now.")
