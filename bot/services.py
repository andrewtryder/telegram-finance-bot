import asyncio
import html
import math
import zoneinfo
from datetime import datetime, timezone

import yfinance as yf
from cachetools import TTLCache

from .chart import render_chart
from .config import logger

try:
    EASTERN_TZ = zoneinfo.ZoneInfo("America/New_York")
except Exception:
    EASTERN_TZ = timezone.utc

# Quote cache (yfinance symbol -> info dict)
QUOTE_CACHE = TTLCache(maxsize=100, ttl=60)
# Search cache (query -> list of quote dicts)
SEARCH_CACHE = TTLCache(maxsize=200, ttl=300)


def format_et_time(epoch_seconds: int | float | None) -> str:
    """Format Unix epoch timestamp into US Eastern Time (e.g. 8:42 AM ET)."""
    if not epoch_seconds:
        return ""
    try:
        dt = datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).astimezone(EASTERN_TZ)
        hour = dt.hour % 12 or 12
        minute = f"{dt.minute:02d}"
        ampm = "AM" if dt.hour < 12 else "PM"
        return f"{hour}:{minute} {ampm} ET"
    except Exception:
        return ""


async def search_symbols(query: str, max_results: int = 5) -> list[dict]:
    """Search Yahoo Finance for symbols matching a free-text query."""
    from .utils import execute_provider_call

    cache_key = (query.lower().strip(), max_results)
    if cache_key in SEARCH_CACHE:
        logger.info(f"Search cache hit for: {query!r}")
        return SEARCH_CACHE[cache_key]

    def call_search():
        result = yf.Search(
            query,
            max_results=max_results,
            news_count=0,
            lists_count=0,
            include_research=False,
            include_nav_links=False,
            raise_errors=False,
        )
        return result.quotes or []

    try:
        quotes = await execute_provider_call(asyncio.to_thread, call_search)
    except Exception as e:
        logger.error(f"yfinance search error for {query!r}: {e}")
        return []

    SEARCH_CACHE[cache_key] = quotes
    return quotes


def _fetch_yfinance_info(yfinance_symbol: str) -> dict:
    """Fetches a targeted payload combining info and fast_info."""
    try:
        t = yf.Ticker(yfinance_symbol)
        result = {}

        # 1. Base info
        try:
            info_data = t.info
            if isinstance(info_data, dict):
                result.update(info_data)
        except Exception as e:
            logger.warning(f"Could not fetch info for {yfinance_symbol}: {e}")

        # 2. Fast Info (Overrides overlapping fast fields)
        try:
            for k in t.fast_info.keys():
                val = t.fast_info[k]
                if val is not None and str(val).lower() != "nan":
                    result[k] = val
        except Exception as e:
            logger.warning(f"Could not fetch fast_info for {yfinance_symbol}: {e}")

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
    try:
        price = float(price)
    except (TypeError, ValueError):
        return "N/A"

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


def format_compact_quote(info: dict, display_symbol: str, is_crypto: bool = False) -> str:
    """One-line quote for /compare."""
    from .utils import _trend_arrow

    escaped = html.escape(display_symbol.upper())
    if not info:
        return f"<b>{escaped}</b>: Data unavailable"

    price = info.get("lastPrice") or info.get("regularMarketPrice") or info.get("currentPrice")
    if price is None:
        return f"<b>{escaped}</b>: Data unavailable"

    prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
    if prev_close is not None and prev_close != 0:
        change = price - prev_close
        change_pct = (change / prev_close) * 100
    else:
        change = info.get("regularMarketChange", 0.0) or 0.0
        change_pct = info.get("regularMarketChangePercent", 0.0) or 0.0

    sign = "+" if change >= 0 else ""
    arrow = _trend_arrow(change)
    if is_crypto and abs(change) < 1.0:
        change_str = f"{sign}{change:,.4f}"
    else:
        change_str = f"{sign}{change:,.2f}"
    return f"<b>{escaped}</b>: {_format_price(price, is_crypto)}  {arrow} {change_str} ({sign}{change_pct:.2f}%)"


async def get_history_chart_png(yfinance_symbol: str, period: str = "1mo") -> bytes | None:
    """Render a closing-price line chart as PNG bytes without matplotlib."""

    def _render() -> bytes | None:
        t = yf.Ticker(yfinance_symbol)
        hist = t.history(period=period, interval="1d")
        if hist is None or hist.empty or "Close" not in hist.columns:
            return None
        closes = [float(x) for x in hist["Close"] if str(x).lower() != "nan" and math.isfinite(float(x))]
        if len(closes) < 2:
            return None
        timestamps = [int(ts.timestamp()) for ts in hist.index]
        return render_chart(closes, yfinance_symbol.upper(), period.upper(), timestamps=timestamps)

    try:
        return await asyncio.to_thread(_render)
    except Exception as e:
        logger.error(f"Error rendering chart for {yfinance_symbol}: {e}")
        return None


async def get_quote_formatted(yfinance_symbol: str, display_symbol: str | None = None, is_crypto: bool = False) -> str:
    """Format full stock or crypto quote with extended-hours pricing."""
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
        icon = "🪙" if is_crypto else "📈"
        title = f"{icon} <b>{escaped_name} ({escaped_display})</b>"

        lines = [title, DIVIDER]

        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        open_price = info.get("open") or info.get("regularMarketOpen")

        if prev_close is not None and prev_close != 0:
            regular_change = price - prev_close
            regular_change_pct = (regular_change / prev_close) * 100
        else:
            regular_change = info.get("regularMarketChange", 0.0) or 0.0
            regular_change_pct = info.get("regularMarketChangePercent", 0.0) or 0.0

        reg_sign = "+" if regular_change >= 0 else ""
        reg_arrow = _trend_arrow(regular_change)

        # Extended hours logic for equities
        if is_crypto or yfinance_symbol.startswith("^"):
            # Crypto and Cash Indices trade with regular continuous sessions
            chg_str = f"{reg_sign}{_format_price(regular_change, is_crypto)} ({reg_sign}{regular_change_pct:.2f}%)"
            lines.append(f"<b>Price:</b> {_format_price(price, is_crypto)}  {reg_arrow} <b>Today:</b> {chg_str}")
            if not is_crypto:
                lines.append("<b>Session:</b> Regular cash index")
            else:
                lines.append("<b>Session:</b> 24/7 continuous trading")
        else:
            # Stocks and ETFs: Evaluate Trading Session & Extended Hours
            state = str(info.get("marketState") or "").upper()
            if not state:
                # Infer by Eastern Time
                now_et = datetime.now(timezone.utc).astimezone(EASTERN_TZ)
                weekday = now_et.weekday()
                if weekday >= 5:
                    state = "CLOSED"
                elif (now_et.hour, now_et.minute) < (4, 0):
                    state = "CLOSED"
                elif (now_et.hour, now_et.minute) < (9, 30):
                    state = "PRE"
                elif (now_et.hour, now_et.minute) < (16, 0):
                    state = "REGULAR"
                elif (now_et.hour, now_et.minute) < (20, 0):
                    state = "POST"
                else:
                    state = "CLOSED"

            pre_price = info.get("preMarketPrice")
            post_price = info.get("postMarketPrice")
            reg_time = info.get("regularMarketTime")
            pre_time = info.get("preMarketTime")
            post_time = info.get("postMarketTime")

            # Validate pre-market: must not be older than regular market time if regular traded
            pre_valid = (
                pre_price is not None
                and float(pre_price) > 0
                and (not reg_time or not pre_time or pre_time >= reg_time - 86400)
            )
            # Validate post-market: must be from the current session (post_time >= reg_time)
            post_valid = (
                post_price is not None
                and float(post_price) > 0
                and (not reg_time or not post_time or post_time >= reg_time)
            )

            if state in ("PRE", "PREPRE") and pre_valid:
                # Active Pre-Market Session
                ref_close = prev_close or price
                pre_p = float(pre_price)
                pre_change = info.get("preMarketChange")
                if pre_change is None and ref_close:
                    pre_change = pre_p - ref_close
                pre_change = pre_change or 0.0

                pre_pct = info.get("preMarketChangePercent")
                if pre_pct is None and ref_close and ref_close != 0:
                    pre_pct = (pre_change / ref_close) * 100
                pre_pct = pre_pct or 0.0

                pre_sign = "+" if pre_change >= 0 else ""
                pre_arrow = _trend_arrow(pre_change)
                as_of = format_et_time(pre_time or reg_time)

                lines.append(f"<b>Regular Price:</b> {_format_price(price, False)}")
                if prev_close:
                    lines.append(f"<b>Previous Close:</b> {_format_price(prev_close, False)}")
                lines.append("")
                lines.append(f"🌅 <b>Pre-Market:</b> {_format_price(pre_p, False)}")
                lines.append(f"<b>Change:</b> {pre_arrow} {pre_sign}{pre_change:,.2f} ({pre_sign}{pre_pct:.2f}%)")
                if as_of:
                    lines.append(f"<b>As of:</b> {as_of}")
                lines.append("<b>Session:</b> Pre-market")

            elif state in ("POST", "POSTPOST") and post_valid:
                # Active After-Hours Session
                ref_close = price  # regular market close
                post_p = float(post_price)
                post_change = info.get("postMarketChange")
                if post_change is None and ref_close:
                    post_change = post_p - ref_close
                post_change = post_change or 0.0

                post_pct = info.get("postMarketChangePercent")
                if post_pct is None and ref_close and ref_close != 0:
                    post_pct = (post_change / ref_close) * 100
                post_pct = post_pct or 0.0

                post_sign = "+" if post_change >= 0 else ""
                post_arrow = _trend_arrow(post_change)
                as_of = format_et_time(post_time or reg_time)

                lines.append(f"<b>Regular Close:</b> {_format_price(price, False)}")
                lines.append("")
                lines.append(f"🌙 <b>After-Hours:</b> {_format_price(post_p, False)}")
                lines.append(f"<b>Change:</b> {post_arrow} {post_sign}{post_change:,.2f} ({post_sign}{post_pct:.2f}%)")
                if as_of:
                    lines.append(f"<b>As of:</b> {as_of}")
                lines.append("<b>Session:</b> After-hours")

            elif state == "REGULAR":
                # Regular Trading Session
                chg_str = f"{reg_sign}{_format_price(regular_change, False)} ({reg_sign}{regular_change_pct:.2f}%)"
                lines.append(f"<b>Price:</b> {_format_price(price, False)}  {reg_arrow} <b>Today:</b> {chg_str}")
                open_close_bits = []
                if prev_close:
                    open_close_bits.append(f"Prev Close {_format_price(prev_close, False)}")
                if open_price:
                    open_close_bits.append(f"Open {_format_price(open_price, False)}")
                if open_close_bits:
                    lines.append(" · ".join(open_close_bits))
                lines.append("<b>Session:</b> Regular market")

            else:
                # Closed Session
                chg_str = f"{reg_sign}{_format_price(regular_change, False)} ({reg_sign}{regular_change_pct:.2f}%)"
                p_fmt = _format_price(price, False)
                lines.append(f"<b>Regular Close:</b> {p_fmt}  {reg_arrow} <b>Today:</b> {chg_str}")
                if post_valid:
                    post_p = float(post_price)
                    post_change = info.get("postMarketChange")
                    if post_change is None and price:
                        post_change = post_p - price
                    post_change = post_change or 0.0
                    post_pct = info.get("postMarketChangePercent")
                    if post_pct is None and price and price != 0:
                        post_pct = (post_change / price) * 100
                    post_pct = post_pct or 0.0
                    post_sign = "+" if post_change >= 0 else ""
                    as_of = format_et_time(post_time)
                    lines.append(
                        f"🌙 <b>After-Hours Close:</b> {_format_price(post_p, False)} ({post_sign}{post_pct:.2f}%)"
                        + (f" as of {as_of}" if as_of else "")
                    )
                lines.append("<b>Session:</b> Closed")

        # Ranges
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

        # Volume & Market Cap
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

        # Meta & Timestamps
        meta_bits = []
        exchange = info.get("exchange")
        if exchange and not is_crypto:
            meta_bits.append(html.escape(str(exchange)))

        currency = info.get("currency")
        if currency:
            meta_bits.append(html.escape(str(currency)))

        market_time = _format_market_time(info)
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
