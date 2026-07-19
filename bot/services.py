import asyncio
import html

import yfinance as yf
from cachetools import TTLCache

from .config import logger

# Quote cache (yfinance symbol -> info dict)
QUOTE_CACHE = TTLCache(maxsize=100, ttl=60)
# Search cache (query -> list of quote dicts)
SEARCH_CACHE = TTLCache(maxsize=200, ttl=300)


async def search_symbols(query: str, max_results: int = 5) -> list[dict]:
    """Search Yahoo Finance for symbols matching a free-text query.

    Returns Yahoo-native symbols, so results can be passed straight into
    /stock, /crypto, /chart, /compare, or /watchlist without translation.
    """
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


def _format_extended_hours(info: dict) -> str | None:
    """Compact pre/post-market line when Yahoo exposes extended-session prices."""
    from .utils import _trend_arrow

    state = str(info.get("marketState") or "").upper()
    pre_price = info.get("preMarketPrice")
    post_price = info.get("postMarketPrice")

    if state == "PRE" or (pre_price is not None and state not in ("REGULAR", "CLOSED", "POST")):
        price = pre_price
        change = info.get("preMarketChange", 0.0) or 0.0
        change_pct = info.get("preMarketChangePercent", 0.0) or 0.0
        label = "Pre"
        icon = "🌅"
    elif state == "POST" or (post_price is not None and state != "REGULAR"):
        price = post_price
        change = info.get("postMarketChange", 0.0) or 0.0
        change_pct = info.get("postMarketChangePercent", 0.0) or 0.0
        label = "Post"
        icon = "🌙"
    elif pre_price is not None and state not in ("REGULAR",):
        price = pre_price
        change = info.get("preMarketChange", 0.0) or 0.0
        change_pct = info.get("preMarketChangePercent", 0.0) or 0.0
        label = "Pre"
        icon = "🌅"
    elif post_price is not None:
        price = post_price
        change = info.get("postMarketChange", 0.0) or 0.0
        change_pct = info.get("postMarketChangePercent", 0.0) or 0.0
        label = "Post"
        icon = "🌙"
    else:
        return None

    if price is None:
        return None

    sign = "+" if change >= 0 else ""
    arrow = _trend_arrow(change)
    return (
        f"{icon} <b>{label}:</b> {_format_price(price, False)}  "
        f"{arrow} {sign}{_format_price(change, False)} ({sign}{change_pct:.2f}%)"
    )


def format_compact_quote(info: dict, display_symbol: str, is_crypto: bool = False) -> str:
    """One-line quote for compare / watchlist."""
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
    """Render a simple closing-price line chart as PNG bytes."""
    import asyncio
    from io import BytesIO

    def _render() -> bytes | None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import yfinance as yf

        hist = yf.Ticker(yfinance_symbol).history(period=period, interval="1d")
        if hist is None or hist.empty or "Close" not in hist.columns:
            return None

        fig, ax = plt.subplots(figsize=(8, 4), dpi=120)
        bg = "#0f1419"
        line = "#38bdf8"
        fig.patch.set_facecolor(bg)
        ax.set_facecolor(bg)
        closes = hist["Close"]
        ax.plot(hist.index, closes, color=line, linewidth=1.8)
        ax.fill_between(hist.index, closes, alpha=0.25, color=line)
        ax.set_title(f"{yfinance_symbol.upper()} ({period})", color="#e2e8f0", fontsize=12)
        ax.set_ylabel("Close", color="#94a3b8")
        ax.tick_params(colors="#94a3b8", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#1e293b")
        ax.grid(True, alpha=0.2, color="#475569")
        fig.autofmt_xdate()
        fig.tight_layout()

        buf = BytesIO()
        fig.savefig(buf, format="png", facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    try:
        return await asyncio.to_thread(_render)
    except Exception as e:
        logger.error(f"Error rendering chart for {yfinance_symbol}: {e}")
        return None


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
            extended = _format_extended_hours(info)
            if extended:
                lines.append(extended)

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
