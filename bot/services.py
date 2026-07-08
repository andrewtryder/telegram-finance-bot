import asyncio
import html

import httpx
import yfinance as yf
from cachetools import TTLCache

from .config import logger

# API Cache: (url, redacted_params_tuple) -> data
API_CACHE = TTLCache(maxsize=100, ttl=600)
# Quote cache (yfinance symbol -> info dict)
QUOTE_CACHE = TTLCache(maxsize=100, ttl=60)

# Shared HTTP client
HTTP_CLIENT = None


async def init_http_client():
    global HTTP_CLIENT
    from .config import PROVIDER_TIMEOUT

    headers = {"User-Agent": "TelegramStockPriceBot/1.0.0"}
    HTTP_CLIENT = httpx.AsyncClient(timeout=PROVIDER_TIMEOUT, headers=headers)
    logger.info("Shared HTTP client initialized")


async def close_http_client():
    global HTTP_CLIENT
    if HTTP_CLIENT:
        await HTTP_CLIENT.aclose()
        logger.info("Shared HTTP client closed")


def _make_safe_cache_key(url: str, params: dict | None) -> tuple:
    if not params:
        return (url, ())
    safe_params = []
    for k, v in sorted(params.items()):
        if k in ("apikey", "api_key", "token", "key"):
            safe_params.append((k, "[REDACTED]"))
        else:
            safe_params.append((k, str(v)))
    return (url, tuple(safe_params))


async def fetch_with_cache(url: str, params: dict | None = None) -> dict:
    from .utils import execute_provider_call

    cache_key = _make_safe_cache_key(url, params)

    if cache_key in API_CACHE:
        logger.info("⚡ Cache HIT for API query (secrets redacted)")
        return API_CACHE[cache_key]

    logger.info("🐢 Cache MISS for API query (secrets redacted) - fetching from API")
    global HTTP_CLIENT

    async def _do_fetch():
        if HTTP_CLIENT and not HTTP_CLIENT.is_closed:
            response = await HTTP_CLIENT.get(url, params=params)
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    data = await execute_provider_call(_do_fetch)
    API_CACHE[cache_key] = data
    return data


def _fetch_yfinance_info(yfinance_symbol: str) -> dict:
    try:
        t = yf.Ticker(yfinance_symbol)
        info = t.info
        return info
    except Exception as e:
        logger.error(f"yfinance info error for {yfinance_symbol}: {e}")
        return {}


async def _get_yfinance_info(yfinance_symbol: str) -> dict:
    from .utils import execute_provider_call

    if yfinance_symbol in QUOTE_CACHE:
        logger.info(f"Quote cache hit for: {yfinance_symbol}")
        return QUOTE_CACHE[yfinance_symbol]

    logger.info(f"Quote cache miss for: {yfinance_symbol}, fetching via yfinance...")

    def call_yf():
        return _fetch_yfinance_info(yfinance_symbol)

    info = await execute_provider_call(asyncio.to_thread, call_yf)
    if info:
        QUOTE_CACHE[yfinance_symbol] = info
    return info


async def _get_yfinance_news(symbol: str) -> list:
    from .utils import execute_provider_call

    def call_news():
        t = yf.Ticker(symbol)
        return t.news

    try:
        return await execute_provider_call(asyncio.to_thread, call_news)
    except Exception as e:
        logger.error(f"Error fetching news for {symbol}: {e}")
        return []


def _first_present(info: dict, *keys: str):
    for key in keys:
        value = info.get(key)
        if value is not None:
            return value
    return None


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def get_quote_formatted(yfinance_symbol: str, display_symbol: str | None = None) -> str:
    from .utils import _format_large_number, _format_market_time, _format_money, _format_plain_number

    display_symbol = display_symbol or yfinance_symbol
    try:
        info = await _get_yfinance_info(yfinance_symbol)
        escaped_display = html.escape(display_symbol.upper())
        if not info:
            return f"Could not find data for <b>{escaped_display}</b>."

        price = _first_present(info, "regularMarketPrice", "currentPrice")
        price_num = _to_float(price)
        if price_num is None:
            return f"Could not fetch current price for <b>{escaped_display}</b>."

        name = info.get("shortName") or info.get("longName") or display_symbol
        escaped_name = html.escape(name)
        currency = info.get("financialCurrency") or info.get("currency") or "USD"

        prev_close = _first_present(info, "previousClose", "regularMarketPreviousClose")
        prev_close_num = _to_float(prev_close)
        if prev_close_num not in (None, 0):
            change = price_num - prev_close_num
            change_pct = (change / prev_close_num) * 100
        else:
            change = _to_float(info.get("regularMarketChange")) or 0.0
            change_pct = _to_float(info.get("regularMarketChangePercent")) or 0.0

        sign = "+" if change >= 0 else "-"
        lines = [
            f"📈 <b>{escaped_name} ({escaped_display})</b>",
            f"<b>Price:</b> {html.escape(_format_money(price_num, currency))}",
            f"<b>Change:</b> {sign}{html.escape(_format_money(abs(change), currency))} ({sign}{abs(change_pct):.2f}%)",
        ]

        open_price = _first_present(info, "regularMarketOpen", "open")
        if prev_close is not None or open_price is not None:
            lines.append(
                "<b>Previous Close / Open:</b> "
                f"{html.escape(_format_money(prev_close, currency))} / "
                f"{html.escape(_format_money(open_price, currency))}"
            )

        day_low = _first_present(info, "regularMarketDayLow", "dayLow")
        day_high = _first_present(info, "regularMarketDayHigh", "dayHigh")
        if day_low is not None or day_high is not None:
            lines.append(
                "<b>Day Range:</b> "
                f"{html.escape(_format_money(day_low, currency))} - {html.escape(_format_money(day_high, currency))}"
            )

        low52 = info.get("fiftyTwoWeekLow")
        high52 = info.get("fiftyTwoWeekHigh")
        if low52 is not None or high52 is not None:
            lines.append(
                "<b>52W Range:</b> "
                f"{html.escape(_format_money(low52, currency))} - {html.escape(_format_money(high52, currency))}"
            )

        volume = _first_present(info, "regularMarketVolume", "volume")
        average_volume = _first_present(info, "averageVolume", "averageDailyVolume10Day")
        if volume is not None or average_volume is not None:
            lines.append(
                "<b>Volume / Avg Volume:</b> "
                f"{html.escape(_format_plain_number(volume))} / {html.escape(_format_plain_number(average_volume))}"
            )

        market_cap = info.get("marketCap")
        if market_cap is not None:
            lines.append(f"<b>Market Cap:</b> {html.escape(_format_large_number(market_cap))}")

        exchange = info.get("fullExchangeName") or info.get("exchange")
        market_state = info.get("marketState")
        meta_parts = []
        if exchange:
            meta_parts.append(html.escape(str(exchange)))
        if currency:
            meta_parts.append(html.escape(str(currency).upper()))
        if market_state:
            meta_parts.append(html.escape(str(market_state)))
        if meta_parts:
            lines.append(f"<b>Exchange / Currency / State:</b> {' / '.join(meta_parts)}")

        market_time = _format_market_time(info)
        if market_time:
            lines.append(f"<b>As of:</b> {html.escape(market_time)}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error getting quote for {yfinance_symbol}: {e}")
        escaped_display = html.escape(display_symbol.upper())
        return f"Sorry, I encountered an error fetching data for <b>{escaped_display}</b>."
