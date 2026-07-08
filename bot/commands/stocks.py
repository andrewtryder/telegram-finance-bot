import html
from datetime import datetime, timezone

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
    _format_money,
    _format_percentage,
    _format_plain_number,
    _truncate_text,
    command_guard,
    send_action,
    validate_url,
)

from .options import get_command_options_text, strip_getopts, wants_getopts


def _format_decimal(value, decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def _first_present(info: dict, *keys: str):
    for key in keys:
        value = info.get(key)
        if value is not None:
            return value
    return None


def _format_news_time(value) -> str:
    if not value:
        return ""
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
        elif isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            return ""
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError):
        return ""


@command_guard
@send_action(ChatAction.TYPING)
async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if wants_getopts(context.args):
        await update.message.reply_text(get_command_options_text("stock"), parse_mode="HTML")
        return

    args = strip_getopts(context.args)
    if not args:
        await update.message.reply_text(
            "Please provide a stock ticker. Example: <code>/stock AAPL</code>\n"
            "Use <code>/stock --getopts</code> for command details.",
            parse_mode="HTML",
        )
        return

    ticker = args[0]
    if not validate_stock_ticker(ticker):
        await update.message.reply_text(
            "Invalid stock ticker format. Tickers must be up to 16 alphanumeric "
            "characters, dots, dashes, equal signs, or carets.",
            parse_mode="HTML",
        )
        return

    yfinance_symbol = to_yfinance_stock(ticker)

    text = await get_quote_formatted(yfinance_symbol, display_symbol=ticker.upper())
    await update.message.reply_text(text, parse_mode="HTML")


@command_guard
@send_action(ChatAction.TYPING)
async def stockinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if wants_getopts(context.args):
        await update.message.reply_text(get_command_options_text("stockinfo"), parse_mode="HTML")
        return

    args = strip_getopts(context.args)
    if not args:
        await update.message.reply_text(
            "Please provide a stock ticker. Example: <code>/stockinfo AAPL</code>\n"
            "Use <code>/stockinfo --getopts</code> for command details.",
            parse_mode="HTML",
        )
        return

    ticker = args[0]
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
        country = info.get("country", "N/A")
        exchange = info.get("fullExchangeName") or info.get("exchange") or "N/A"
        currency = info.get("financialCurrency") or info.get("currency") or "USD"
        market_cap = _format_large_number(info.get("marketCap"))
        revenue = _format_large_number(info.get("totalRevenue"))
        employees = _format_plain_number(info.get("fullTimeEmployees"))
        pe_str = _format_decimal(_first_present(info, "trailingPE", "forwardPE"))
        eps_str = _format_money(_first_present(info, "trailingEps", "forwardEps"), currency)
        beta_str = _format_decimal(info.get("beta"))
        profit_margin = _format_percentage(info.get("profitMargins"))

        div_yield = info.get("dividendYield")
        div_str = _format_percentage(div_yield) if div_yield is not None else "N/A"

        high52 = info.get("fiftyTwoWeekHigh")
        high52_str = _format_money(high52, currency) if high52 is not None else "N/A"

        low52 = info.get("fiftyTwoWeekLow")
        low52_str = _format_money(low52, currency) if low52 is not None else "N/A"

        summary = _truncate_text(info.get("longBusinessSummary") or info.get("description") or "No summary available.")
        website = info.get("website")

        escaped_name = html.escape(name)
        escaped_symbol = html.escape(yfinance_symbol)
        escaped_sector = html.escape(sector)
        escaped_industry = html.escape(industry)
        escaped_country = html.escape(country)
        escaped_exchange = html.escape(exchange)
        escaped_currency = html.escape(str(currency).upper())
        escaped_summary = html.escape(summary)

        lines = [
            f"ℹ️ <b>{escaped_name} ({escaped_symbol})</b>",
            f"<b>Sector / Industry:</b> {escaped_sector} / {escaped_industry}",
            f"<b>Country / Exchange:</b> {escaped_country} / {escaped_exchange}",
            f"<b>Currency:</b> {escaped_currency}",
            "",
            f"<b>Market Cap:</b> {html.escape(market_cap)}",
            f"<b>Total Revenue:</b> {html.escape(revenue)}",
            f"<b>Employees:</b> {html.escape(employees)}",
            f"<b>P/E Ratio:</b> {html.escape(pe_str)}",
            f"<b>EPS:</b> {html.escape(eps_str)}",
            f"<b>Beta:</b> {html.escape(beta_str)}",
            f"<b>Profit Margin:</b> {html.escape(profit_margin)}",
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

    if wants_getopts(context.args):
        await update.message.reply_text(get_command_options_text("stocknews"), parse_mode="HTML")
        return

    args = strip_getopts(context.args)
    if not args:
        await update.message.reply_text(
            "Please provide a stock ticker. Example: <code>/stocknews AAPL</code>\n"
            "Use <code>/stocknews --getopts</code> for command details.",
            parse_mode="HTML",
        )
        return

    ticker = args[0]
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
        for index, item in enumerate(news_items[:5], start=1):
            content = item.get("content") if isinstance(item.get("content"), dict) else item
            title = content.get("title") or item.get("title") or "No Title"
            provider = (
                content.get("provider", {}).get("displayName")
                if isinstance(content.get("provider"), dict)
                else None
            )
            provider = provider or content.get("providerDisplayName") or item.get("publisher")
            published = _format_news_time(content.get("pubDate") or item.get("providerPublishTime"))

            url = ""
            if isinstance(content.get("clickThroughUrl"), dict):
                url = content["clickThroughUrl"].get("url", "")
            elif content.get("canonicalUrl") and isinstance(content.get("canonicalUrl"), dict):
                url = content["canonicalUrl"].get("url", "")
            elif "link" in item:
                url = item["link"]

            escaped_title = html.escape(title)
            if validate_url(url):
                escaped_url = html.escape(url)
                lines.append(f'{index}. <a href="{escaped_url}">{escaped_title}</a>')
            else:
                lines.append(f"{index}. {escaped_title}")

            metadata = [part for part in (provider, published) if part]
            if metadata:
                lines.append(f"   <i>{html.escape(' • '.join(metadata))}</i>")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error fetching news for {yfinance_symbol}: {e}")
        await update.message.reply_text("Sorry, I couldn't fetch news for that symbol right now.")


@command_guard
@send_action(ChatAction.TYPING)
async def marketcap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command_text = update.message.text
    logger.info(f"Command received: {command_text} from {update.effective_user.first_name}")

    if wants_getopts(context.args):
        await update.message.reply_text(get_command_options_text("marketcap"), parse_mode="HTML")
        return

    args = strip_getopts(context.args)
    if not args:
        await update.message.reply_text(
            "Please provide a stock ticker. Example: <code>/marketcap AAPL</code>\n"
            "Use <code>/marketcap --getopts</code> for command details.",
            parse_mode="HTML",
        )
        return

    ticker = args[0]
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
        enterprise_value = _format_large_number(info.get("enterpriseValue"))
        shares_outstanding = _format_plain_number(info.get("sharesOutstanding"))
        exchange = info.get("fullExchangeName") or info.get("exchange") or "N/A"
        currency = info.get("financialCurrency") or info.get("currency") or "USD"

        lines = [
            f"💰 <b>{html.escape(name)} ({html.escape(yfinance_symbol)})</b>",
            f"<b>Market Cap:</b> {html.escape(market_cap)}",
            f"<b>Enterprise Value:</b> {html.escape(enterprise_value)}",
            f"<b>Shares Outstanding:</b> {html.escape(shares_outstanding)}",
            f"<b>Exchange / Currency:</b> {html.escape(exchange)} / {html.escape(str(currency).upper())}",
        ]
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error fetching market cap for {yfinance_symbol}: {e}")
        await update.message.reply_text("Sorry, I couldn't fetch data for that symbol right now.")
