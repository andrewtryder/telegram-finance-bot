import httpx
import asyncio
import yfinance as yf
from cachetools import TTLCache
from .config import logger

# API Cache (URL -> data)
API_CACHE = TTLCache(maxsize=100, ttl=600)
# Quote cache (yfinance symbol -> info dict)
QUOTE_CACHE = TTLCache(maxsize=100, ttl=60)

async def fetch_with_cache(url: str) -> dict:
    if url in API_CACHE:
        logger.info(f"Cache hit for URL: {url}")
        return API_CACHE[url]

    logger.info(f"Cache miss for URL: {url}, fetching...")
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        API_CACHE[url] = data
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
    if yfinance_symbol in QUOTE_CACHE:
        logger.info(f"Quote cache hit for: {yfinance_symbol}")
        return QUOTE_CACHE[yfinance_symbol]

    logger.info(f"Quote cache miss for: {yfinance_symbol}, fetching via yfinance...")
    info = await asyncio.to_thread(_fetch_yfinance_info, yfinance_symbol)
    if info:
        QUOTE_CACHE[yfinance_symbol] = info
    return info

def _fetch_yfinance_news(symbol: str) -> list:
    try:
        t = yf.Ticker(symbol)
        return t.news
    except Exception as e:
        logger.error(f"yfinance news error for {symbol}: {e}")
        return []

async def get_quote_formatted(yfinance_symbol: str, display_symbol: str | None = None) -> str:
    from .utils import _format_market_time
    display_symbol = display_symbol or yfinance_symbol
    try:
        info = await _get_yfinance_info(yfinance_symbol)
        if not info:
            return f"Could not find data for **{display_symbol}**."

        price = info.get("regularMarketPrice") or info.get("currentPrice")
        if price is None:
            return f"Could not fetch current price for **{display_symbol}**."

        prev_close = info.get("previousClose")
        if prev_close is not None and prev_close != 0:
            change = price - prev_close
            change_pct = (change / prev_close) * 100
        else:
            change = 0.0
            change_pct = 0.0

        market_time = _format_market_time(info)
        time_str = f" (As of {market_time})" if market_time else ""

        sign = "+" if change >= 0 else ""
        lines = [
            f"📈 **{display_symbol}**",
            f"**Price:** ${price:,.2f}{time_str}",
            f"**Change:** {sign}${change:,.2f} ({sign}{change_pct:.2f}%)",
        ]

        if "regularMarketDayHigh" in info and "regularMarketDayLow" in info:
            high = info["regularMarketDayHigh"]
            low = info["regularMarketDayLow"]
            lines.append(f"**Day Range:** ${low:,.2f} - ${high:,.2f}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error getting quote for {yfinance_symbol}: {e}")
        return f"Sorry, I encountered an error fetching data for **{display_symbol}**."
