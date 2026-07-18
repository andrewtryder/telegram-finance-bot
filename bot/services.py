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
    """Fetches a rich payload combining fast_info, info, and history for quotes."""
    try:
        t = yf.Ticker(yfinance_symbol)

        result = {}

        # 1. Base info (still needed for name, sector, etc.)
        try:
            result.update(t.info)
        except Exception as e:
            logger.warning(f"Could not fetch info for {yfinance_symbol}: {e}")

        # 2. Fast Info (Overrides overlapping info fields)
        try:
            for k in t.fast_info.keys():
                val = t.fast_info[k]
                if val is not None and not str(val).lower() == "nan":
                    result[k] = val
        except Exception as e:
            logger.warning(f"Could not fetch fast_info for {yfinance_symbol}: {e}")

        # 3. 5-day history for week range
        try:
            hist_5d = t.history(period="5d", interval="1d")
            if not hist_5d.empty:
                result["weekHigh"] = float(hist_5d["High"].max())
                result["weekLow"] = float(hist_5d["Low"].min())
        except Exception as e:
            logger.warning(f"Could not fetch 5d history for {yfinance_symbol}: {e}")

        # 4. Fallback for 52W range if fast_info missed it
        if "yearHigh" not in result or "yearLow" not in result:
            try:
                hist_1y = t.history(period="1y", interval="1d")
                if not hist_1y.empty:
                    result["yearHigh"] = float(hist_1y["High"].max())
                    result["yearLow"] = float(hist_1y["Low"].min())
            except Exception as e:
                logger.warning(f"Could not fetch 1y history for {yfinance_symbol}: {e}")

        return result
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
        try:
            return t.get_news(count=10)
        except AttributeError:
            return t.news

    try:
        return await execute_provider_call(asyncio.to_thread, call_news)
    except Exception as e:
        logger.error(f"Error fetching news for {symbol}: {e}")
        return []


def _format_price(price, is_crypto: bool) -> str:
    if price is None:
        return "N/A"

    # Format crypto with more precision if it's cheap
    if is_crypto and price < 1.0:
        return f"${price:,.4f}"
    return f"${price:,.2f}"


def _format_volume(vol) -> str:
    from .utils import _format_large_number

    if not vol or str(vol).lower() == "nan":
        return "N/A"
    try:
        return _format_large_number(vol).replace("$", "")
    except Exception:
        return "N/A"


async def get_quote_formatted(yfinance_symbol: str, display_symbol: str | None = None, is_crypto: bool = False) -> str:
    from .utils import DIVIDER, _format_large_number, _format_market_time, _trend_arrow

    display_symbol = display_symbol or yfinance_symbol
    try:
        info = await _get_yfinance_info(yfinance_symbol)
        escaped_display = html.escape(display_symbol.upper())
        if not info:
            return f"Could not find data for <b>{escaped_display}</b>."

        price = info.get("lastPrice") or info.get("regularMarketPrice") or info.get("currentPrice")
        if price is None:
            return f"Could not fetch current price for <b>{escaped_display}</b>."

        name = info.get("shortName") or info.get("longName") or display_symbol
        escaped_name = html.escape(name)

        # Crypto emoji vs Stock emoji
        icon = "🪙" if is_crypto else "📈"
        title = f"{icon} <b>{escaped_name} ({escaped_display})</b>"

        lines = [title, DIVIDER]

        # Price and Change, combined onto one line
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        open_price = info.get("open") or info.get("regularMarketOpen")

        if prev_close is not None and prev_close != 0:
            change = price - prev_close
            change_pct = (change / prev_close) * 100
        else:
            # Fallback if fast_info provides them (though fast_info doesn't have change directly)
            change = info.get("regularMarketChange", 0.0)
            change_pct = info.get("regularMarketChangePercent", 0.0)

        sign = "+" if change >= 0 else ""
        arrow = _trend_arrow(change)

        lines.append(
            f"<b>Price:</b> {_format_price(price, is_crypto)}  "
            f"{arrow} <b>Today:</b> {sign}{_format_price(change, is_crypto)} ({sign}{change_pct:.2f}%)"
        )

        if not is_crypto:
            open_close_bits = []
            if prev_close:
                open_close_bits.append(f"Prev Close {_format_price(prev_close, False)}")
            if open_price:
                open_close_bits.append(f"Open {_format_price(open_price, False)}")
            if open_close_bits:
                lines.append(" · ".join(open_close_bits))

        # Ranges, folded onto one line
        range_bits = []
        day_high = info.get("dayHigh") or info.get("regularMarketDayHigh")
        day_low = info.get("dayLow") or info.get("regularMarketDayLow")
        if day_high is not None and day_low is not None:
            range_bits.append(f"Day {_format_price(day_low, is_crypto)}–{_format_price(day_high, is_crypto)}")

        week_high = info.get("weekHigh")
        week_low = info.get("weekLow")
        if week_high is not None and week_low is not None:
            range_bits.append(f"Week {_format_price(week_low, is_crypto)}–{_format_price(week_high, is_crypto)}")

        year_high = info.get("yearHigh") or info.get("fiftyTwoWeekHigh")
        year_low = info.get("yearLow") or info.get("fiftyTwoWeekLow")
        if year_high is not None and year_low is not None:
            range_bits.append(f"52W {_format_price(year_low, is_crypto)}–{_format_price(year_high, is_crypto)}")

        if range_bits:
            lines.append(f"📊 <b>Range:</b> {' · '.join(range_bits)}")

        # Volume & Market Cap, folded onto one line
        stat_bits = []
        volume = info.get("lastVolume") or info.get("regularMarketVolume") or info.get("volume")
        if volume:
            stat_bits.append(f"Vol {_format_volume(volume)}")

        if not is_crypto:
            avg_vol = info.get("threeMonthAverageVolume") or info.get("averageVolume")
            if avg_vol:
                stat_bits.append(f"Avg Vol {_format_volume(avg_vol)}")

            mcap = info.get("marketCap")
            if mcap:
                stat_bits.append(f"Cap {_format_large_number(mcap)}")

        if stat_bits:
            lines.append(f"📦 {' · '.join(stat_bits)}")

        # Meta, folded onto one line
        meta_bits = []
        exchange = info.get("exchange")
        if exchange and not is_crypto:
            meta_bits.append(html.escape(str(exchange)))

        currency = info.get("currency")
        if currency:
            meta_bits.append(html.escape(str(currency)))

        market_time = _format_market_time(info)
        # fallback for timezone if time format fails
        tz = info.get("timezone")
        if market_time:
            meta_bits.append(f"as of {html.escape(market_time)}")
        elif tz:
            meta_bits.append(html.escape(str(tz)))

        if meta_bits:
            lines.append(f"<i>{' · '.join(meta_bits)}</i>")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error getting quote for {yfinance_symbol}: {e}")
        escaped_display = html.escape(display_symbol.upper())
        return f"Sorry, I encountered an error fetching data for <b>{escaped_display}</b>."
