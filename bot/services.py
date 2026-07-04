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


async def get_quote_formatted(yfinance_symbol: str, display_symbol: str | None = None) -> str:
    from .utils import _format_market_time

    display_symbol = display_symbol or yfinance_symbol
    try:
        info = await _get_yfinance_info(yfinance_symbol)
        escaped_display = html.escape(display_symbol.upper())
        if not info:
            return f"Could not find data for <b>{escaped_display}</b>."

        price = info.get("regularMarketPrice") or info.get("currentPrice")
        if price is None:
            return f"Could not fetch current price for <b>{escaped_display}</b>."

        name = info.get("shortName") or info.get("longName") or display_symbol
        escaped_name = html.escape(name)

        prev_close = info.get("previousClose")
        if prev_close is not None and prev_close != 0:
            change = price - prev_close
            change_pct = (change / prev_close) * 100
        else:
            change = 0.0
            change_pct = 0.0

        market_time = _format_market_time(info)
        escaped_time = html.escape(market_time)
        time_str = f" (As of {escaped_time})" if market_time else ""

        sign = "+" if change >= 0 else ""
        lines = [
            f"📈 <b>{escaped_name} ({escaped_display})</b>",
            f"<b>Price:</b> ${price:,.2f}{time_str}",
            f"<b>Change:</b> {sign}${change:,.2f} ({sign}{change_pct:.2f}%)",
        ]

        if "regularMarketDayHigh" in info and "regularMarketDayLow" in info:
            high = info["regularMarketDayHigh"]
            low = info["regularMarketDayLow"]
            lines.append(f"<b>Day Range:</b> ${low:,.2f} - ${high:,.2f}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error getting quote for {yfinance_symbol}: {e}")
        escaped_display = html.escape(display_symbol.upper())
        return f"Sorry, I encountered an error fetching data for <b>{escaped_display}</b>."
