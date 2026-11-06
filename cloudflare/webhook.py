"""Cloudflare Python Worker webhook handler."""

import asyncio
import datetime
import decimal
import hmac
import html
import json
import math
import re
import time
import urllib.parse
import zoneinfo
from collections import OrderedDict
from typing import Any, Optional

try:
    from chart import render_chart
except ImportError:
    from cloudflare.chart import render_chart

try:
    from workers import Response  # type: ignore
    from workers import fetch as cf_fetch
except ImportError:
    cf_fetch = None

    class Response:  # type: ignore
        def __init__(self, body="", status=200, headers=None):
            self.body = body
            self.status = status
            self.headers = headers or {}

        @classmethod
        def json(cls, data, status=200, headers=None):
            h = {"content-type": "application/json"}
            if headers:
                h.update(headers)
            return cls(json.dumps(data), status=status, headers=h)

        async def text(self):
            if isinstance(self.body, bytes):
                return self.body.decode("utf-8")
            return str(self.body)


try:
    EASTERN_TZ = zoneinfo.ZoneInfo("America/New_York")
except Exception:
    EASTERN_TZ = datetime.timezone.utc

COMMANDS = "/stock /stockinfo /stocknews /marketcap /crypto /indices /search /compare /chart /admin"
KNOWN_COMMANDS = set(("start help indicies alert watchlist " + COMMANDS.replace("/", "")).split(" "))
UNAVAILABLE: set[str] = set()
CRYPTO_BASES = set(
    (
        "BTC ETH SOL XRP DOGE ADA AVAX DOT LINK ATOM LTC BCH UNI AAVE PEPE SHIB "
        "TON TRX NEAR APT SUI SEI ARB OP FIL ICP HBAR ALGO XLM VET XMR ETC"
    ).split()
)
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9^.=/-]{1,24}$")
DIVIDER = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"

metrics = {
    "commands": {},
    "errors": 0,
    "provider_errors": 0,
}
recent_updates: OrderedDict[int, None] = OrderedDict()
MAX_CACHE_SIZE = 100
QUOTE_CACHE: OrderedDict[str, tuple[float, dict]] = OrderedDict()
DATA_CACHE: OrderedDict[str, tuple[float, dict]] = OrderedDict()


def _cache_set(cache: OrderedDict, key: Any, value: tuple[float, Any], max_size: int = MAX_CACHE_SIZE) -> None:
    cache[key] = value
    cache.move_to_end(key)
    if len(cache) > max_size:
        cache.popitem(last=False)


def _cache_get(cache: OrderedDict, key: Any) -> Optional[Any]:
    if key not in cache:
        return None
    expire_at, data = cache[key]
    if time.time() > expire_at:
        del cache[key]
        return None
    cache.move_to_end(key)
    return data


def format_et_time(epoch_seconds: int | float | None) -> str:
    """Format Unix epoch timestamp into US Eastern Time with calendar date (e.g. Nov 6, 8:42 AM ET)."""
    if not epoch_seconds:
        return ""
    try:
        dt = datetime.datetime.fromtimestamp(epoch_seconds, tz=datetime.timezone.utc).astimezone(EASTERN_TZ)
        hour = dt.hour % 12 or 12
        minute = f"{dt.minute:02d}"
        ampm = "AM" if dt.hour < 12 else "PM"
        return f"{dt.strftime('%b')} {dt.day}, {hour}:{minute} {ampm} ET"
    except Exception:
        return ""


def is_pre_market_fresh(
    pre_price: Optional[float],
    pre_time: Optional[float],
    reg_time: Optional[float] = None,
    now_dt: Optional[datetime.datetime] = None,
) -> bool:
    """Validate that pre-market quote is fresh and belongs to today's active session.

    Rejects missing pre_time, trades from prior days (e.g. Friday pre-market on Monday morning),
    trades outside the 04:00-09:30 ET window, and quotes after regular market traded today.
    """
    if pre_price is None or pre_price <= 0:
        return False
    if pre_time is None or pre_time <= 0:
        return False
    try:
        if now_dt is None:
            now_et = datetime.datetime.now(datetime.timezone.utc).astimezone(EASTERN_TZ)
        elif now_dt.tzinfo is None:
            now_et = now_dt.replace(tzinfo=EASTERN_TZ)
        else:
            now_et = now_dt.astimezone(EASTERN_TZ)

        if now_et.weekday() >= 5:
            return False

        pre_dt = datetime.datetime.fromtimestamp(pre_time, tz=datetime.timezone.utc).astimezone(EASTERN_TZ)
        if pre_dt.date() != now_et.date():
            return False

        pre_tod = (pre_dt.hour, pre_dt.minute)
        if not ((4, 0) <= pre_tod < (9, 30)):
            return False

        if pre_dt > now_et + datetime.timedelta(minutes=5):
            return False

        if reg_time and reg_time > 0:
            reg_dt = datetime.datetime.fromtimestamp(reg_time, tz=datetime.timezone.utc).astimezone(EASTERN_TZ)
            if reg_dt.date() == now_et.date() and (reg_dt.hour, reg_dt.minute) >= (9, 30):
                return False

        return True
    except Exception:
        return False


def is_post_market_fresh(
    post_price: Optional[float],
    post_time: Optional[float],
    reg_time: Optional[float] = None,
    now_dt: Optional[datetime.datetime] = None,
) -> bool:
    """Validate that after-hours quote is fresh and belongs to today's active session.

    Rejects missing post_time, trades from prior days, trades outside the 16:00-20:00 ET window,
    and trades older than regular market close.
    """
    if post_price is None or post_price <= 0:
        return False
    if post_time is None or post_time <= 0:
        return False
    try:
        if now_dt is None:
            now_et = datetime.datetime.now(datetime.timezone.utc).astimezone(EASTERN_TZ)
        elif now_dt.tzinfo is None:
            now_et = now_dt.replace(tzinfo=EASTERN_TZ)
        else:
            now_et = now_dt.astimezone(EASTERN_TZ)

        if now_et.weekday() >= 5:
            return False

        post_dt = datetime.datetime.fromtimestamp(post_time, tz=datetime.timezone.utc).astimezone(EASTERN_TZ)
        if post_dt.date() != now_et.date():
            return False

        post_tod = (post_dt.hour, post_dt.minute)
        if not ((16, 0) <= post_tod <= (20, 5)):
            return False

        if post_dt > now_et + datetime.timedelta(minutes=5):
            return False

        if reg_time and reg_time > 0 and post_time < reg_time:
            return False

        return True
    except Exception:
        return False


def is_post_market_closed_valid(
    post_price: Optional[float],
    post_time: Optional[float],
    reg_time: Optional[float] = None,
) -> bool:
    """Validate that after-hours quote from the latest session is valid to display during closed session."""
    if post_price is None or post_price <= 0:
        return False
    if post_time is None or post_time <= 0:
        return False
    try:
        post_dt = datetime.datetime.fromtimestamp(post_time, tz=datetime.timezone.utc).astimezone(EASTERN_TZ)
        post_tod = (post_dt.hour, post_dt.minute)
        if not ((16, 0) <= post_tod <= (20, 15)):
            return False
        if reg_time and reg_time > 0:
            reg_dt = datetime.datetime.fromtimestamp(reg_time, tz=datetime.timezone.utc).astimezone(EASTERN_TZ)
            if post_dt.date() != reg_dt.date() or post_time < reg_time:
                return False
        return True
    except Exception:
        return False


def _get_env_val(env: Any, key: str, default: str = "") -> str:
    if hasattr(env, key):
        val = getattr(env, key)
        return str(val) if val is not None else default
    if isinstance(env, dict):
        val = env.get(key)
        return str(val) if val is not None else default
    return default


def parse_ids(value: Any) -> set[str]:
    raw_str = str(value or "")
    out = set()
    for item in raw_str.split(","):
        cleaned = item.strip().strip("'\"")
        if cleaned:
            out.add(cleaned)
    return out


def sanitize_url(url: str) -> str:
    """Strip sensitive bot tokens from Telegram API URLs."""
    return re.sub(r"/bot[^/]+/", "/bot<redacted>/", url)


async def timed_fetch(url: str, options: Optional[dict] = None, timeout: float = 10.0) -> Any:
    fetcher = cf_fetch
    if fetcher is None:
        raise RuntimeError("No HTTP fetcher available in this runtime")
    opts = options or {}
    try:
        return await asyncio.wait_for(fetcher(url, opts), timeout=timeout)
    except asyncio.TimeoutError:
        safe_url = sanitize_url(url)
        raise RuntimeError(f"HTTP fetch timed out after {timeout}s: {safe_url}") from None


async def telegram(env: Any, method: str, body: Optional[dict] = None) -> Any:
    token = _get_env_val(env, "TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/{method}"
    payload = json.dumps(body or {})
    response = await timed_fetch(
        url,
        {
            "method": "POST",
            "headers": {"content-type": "application/json"},
            "body": payload,
        },
    )
    text = await response.text()
    data = json.loads(text)
    if getattr(response, "status", 200) >= 400 or not data.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {data}")
    return data.get("result")


async def send_photo(env: Any, chat_id: int, photo: bytes, caption: str) -> None:
    token = _get_env_val(env, "TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    boundary = "----CloudflarePythonWorkerBoundary7MA4YWxk"
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="photo"; filename="chart.png"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode("utf-8")
        + photo
        + f"\r\n--{boundary}--\r\n".encode("utf-8")
    )

    response = await timed_fetch(
        url,
        {
            "method": "POST",
            "headers": {"content-type": f"multipart/form-data; boundary={boundary}"},
            "body": body,
        },
    )
    text = await response.text()
    data = json.loads(text)
    if getattr(response, "status", 200) >= 400 or not data.get("ok"):
        raise RuntimeError(f"Telegram sendPhoto failed: {data}")


async def data_request(path: str, params: dict, ttl: int = 45) -> dict:
    query = urllib.parse.urlencode(params)
    cache_key = f"{path}?{query}"
    cached = _cache_get(DATA_CACHE, cache_key)
    if cached is not None:
        return cached

    url = f"https://query1.finance.yahoo.com/{path}?{query}"
    response = await timed_fetch(url, {"headers": {"User-Agent": "Mozilla/5.0"}})
    if getattr(response, "status", 200) >= 400:
        raise RuntimeError("Market data provider request failed")
    text = await response.text()
    data = json.loads(text)
    _cache_set(DATA_CACHE, cache_key, (time.time() + ttl, data))
    return data


async def company_summary(symbol: str) -> dict:
    headers = {"User-Agent": "Mozilla/5.0"}
    first = await timed_fetch("https://fc.yahoo.com", {"headers": headers, "redirect": "manual"})
    raw_cookie = ""
    if hasattr(first, "headers"):
        if hasattr(first.headers, "get"):
            raw_cookie = first.headers.get("set-cookie") or ""
    cookie = raw_cookie.split(";")[0] if raw_cookie else ""
    if not cookie:
        raise RuntimeError("Yahoo session unavailable")

    session_headers = {"User-Agent": "Mozilla/5.0", "Cookie": cookie}
    crumb_resp = await timed_fetch(
        "https://query1.finance.yahoo.com/v1/test/getcrumb",
        {"headers": session_headers},
    )
    if getattr(crumb_resp, "status", 200) >= 400:
        raise RuntimeError("Yahoo session unavailable")
    crumb = (await crumb_resp.text()).strip()
    if not crumb or len(crumb) > 128:
        raise RuntimeError("Yahoo session unavailable")

    encoded = urllib.parse.quote(symbol)
    url = (
        f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{encoded}"
        f"?modules=price,assetProfile,summaryDetail,defaultKeyStatistics&crumb={urllib.parse.quote(crumb)}"
    )
    response = await timed_fetch(url, {"headers": session_headers})
    if getattr(response, "status", 200) >= 400:
        raise RuntimeError("Yahoo company data unavailable")
    text = await response.text()
    data = json.loads(text)
    res = data.get("quoteSummary", {}).get("result")
    if not res:
        raise RuntimeError("Yahoo company data unavailable")
    return res[0]


def raw_val(value: Any) -> Any:
    if isinstance(value, dict) and "raw" in value:
        return value["raw"]
    return value


def to_number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        val = float(value)
        return val if math.isfinite(val) else None
    except (TypeError, ValueError):
        return None


def market_symbol(raw: Any, crypto: bool = False, infer_crypto: bool = False) -> Optional[str]:
    symbol = str(raw or "").upper()
    if not SYMBOL_PATTERN.match(symbol):
        return None
    if (crypto or (infer_crypto and symbol in CRYPTO_BASES)) and "/" not in symbol and "-" not in symbol:
        return symbol + "-USD"
    return symbol.replace("/", "-")


async def quote(_env: Any, symbol: str) -> dict:
    cached = _cache_get(QUOTE_CACHE, symbol)
    if cached is not None:
        return cached

    data = await data_request(
        f"v8/finance/chart/{urllib.parse.quote(symbol)}",
        {"range": "1d", "interval": "5m", "includePrePost": "true"},
        ttl=45,
    )
    result_list = data.get("chart", {}).get("result") or []
    if not result_list:
        raise RuntimeError("Quote missing")
    result = result_list[0]
    meta = result.get("meta") or {}
    price = to_number(meta.get("regularMarketPrice"))
    if price is None:
        raise RuntimeError("Quote missing")

    quotes = result.get("indicators", {}).get("quote") or [{}]
    bars = quotes[0] if quotes else {}
    times = result.get("timestamp") or []
    closes = bars.get("close") or []
    opens = bars.get("open") or []

    previous = to_number(meta.get("chartPreviousClose") or meta.get("previousClose"))

    # Extract trading period boundaries if provided
    period = meta.get("currentTradingPeriod") or {}
    pre_period = period.get("pre") or {}
    reg_period = period.get("regular") or {}
    post_period = period.get("post") or {}

    pre_start = to_number(pre_period.get("start"))
    pre_end = to_number(pre_period.get("end"))
    reg_start = to_number(reg_period.get("start"))
    post_start = to_number(post_period.get("start"))
    post_end = to_number(post_period.get("end"))

    # Default to meta pre/post values if provided
    pre_price = to_number(meta.get("preMarketPrice"))
    pre_time = to_number(meta.get("preMarketTime"))
    post_price = to_number(meta.get("postMarketPrice"))
    post_time = to_number(meta.get("postMarketTime"))

    open_val = None
    if times:
        for idx, t in enumerate(times):
            tn = to_number(t)
            if tn is None:
                continue
            # First regular session open
            if open_val is None and reg_start is not None and tn >= reg_start:
                if idx < len(opens) and to_number(opens[idx]) is not None:
                    open_val = to_number(opens[idx])
            # Pre-market trade bars
            if pre_start is not None and pre_end is not None and pre_start <= tn < pre_end:
                if idx < len(closes) and to_number(closes[idx]) is not None:
                    pre_price = to_number(closes[idx])
                    pre_time = tn
            # Post-market trade bars
            elif post_start is not None and post_end is not None and post_start <= tn <= post_end:
                if idx < len(closes) and to_number(closes[idx]) is not None:
                    post_price = to_number(closes[idx])
                    post_time = tn

    res = {
        "symbol": symbol,
        "meta": meta,
        "price": price,
        "previous": previous,
        "open": open_val,
        "preMarketPrice": pre_price,
        "preMarketTime": pre_time,
        "postMarketPrice": post_price,
        "postMarketTime": post_time,
    }
    _cache_set(QUOTE_CACHE, symbol, (time.time() + 45, res))
    return res


def format_number(value: float, crypto: bool = False) -> str:
    decimals = 4 if crypto and abs(value) < 1 else 2
    val = round(decimal.Decimal(str(value)), decimals)
    parts = f"{val:,.{decimals}f}".split(".")
    return parts[0] + "." + parts[1]


def format_price(value: Optional[float], currency: Optional[str], crypto: bool = False) -> Optional[str]:
    if value is None:
        return None
    prefix = "$" if currency == "USD" else f"{html.escape(currency)} " if currency else ""
    return f"{prefix}{format_number(value, crypto)}"


def change_text(q: dict, crypto: bool = False) -> str:
    prev = q.get("previous")
    price = q.get("price")
    if prev is None or prev <= 0 or price is None:
        return ""
    change = price - prev
    pct = (change / prev) * 100
    sign = "+" if change > 0 else "-" if change < 0 else ""
    arrow = "🔺" if change > 0 else "🔻" if change < 0 else "▪️"
    currency = q.get("meta", {}).get("currency")
    return f"{arrow} {sign}{format_price(abs(change), currency, crypto)} ({sign}{abs(pct):.2f}%)"


def ranges(q: dict, crypto: bool = False) -> list[str]:
    result = []
    meta = q.get("meta") or {}
    currency = meta.get("currency")

    def add(label, low, high):
        low_n = to_number(low)
        high_n = to_number(high)
        if low_n is not None and high_n is not None:
            result.append(f"{label} {format_price(low_n, currency, crypto)}–{format_price(high_n, currency, crypto)}")

    add("Day", meta.get("regularMarketDayLow"), meta.get("regularMarketDayHigh"))
    add("52W", meta.get("fiftyTwoWeekLow"), meta.get("fiftyTwoWeekHigh"))
    return result


def compact_number(value: Any) -> Optional[str]:
    n = to_number(value)
    if n is None:
        return None
    for threshold, suffix in [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if abs(n) >= threshold:
            return f"{(n / threshold):.2f}{suffix}"
    return f"{n:,.2f}"


def format_quote(q: dict, crypto: bool = False, now_dt: Optional[datetime.datetime] = None) -> str:
    """Format full stock or crypto quote with extended-hours pricing."""
    meta = q.get("meta") or {}
    name = meta.get("shortName") or meta.get("longName") or q["symbol"]
    display = q["symbol"].replace("-", "/") if crypto else q["symbol"]
    lines = [f"{'🪙' if crypto else '📈'} <b>{html.escape(name)} ({html.escape(display)})</b>", DIVIDER]

    price = q["price"]
    prev_close = q.get("previous")
    open_val = q.get("open")
    curr = meta.get("currency")
    p_str = format_price(price, curr, crypto)
    change = change_text(q, crypto)

    company = q.get("company") or {}
    comp_price = company.get("price") or {}

    if crypto or q["symbol"].startswith("^"):
        # Crypto and Cash indices
        lines.append(f"<b>Price:</b> {p_str}{f'  <b>Today:</b> {change}' if change else ''}")
        if crypto:
            lines.append("<b>Session:</b> 24/7 continuous trading")
        else:
            lines.append("<b>Session:</b> Regular cash index")
    else:
        # Equities: evaluate trading session & extended hours
        if now_dt is None:
            now_et = datetime.datetime.now(datetime.timezone.utc).astimezone(EASTERN_TZ)
        elif now_dt.tzinfo is None:
            now_et = now_dt.replace(tzinfo=EASTERN_TZ)
        else:
            now_et = now_dt.astimezone(EASTERN_TZ)

        state = str(meta.get("marketState") or "").upper()
        if not state:
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

        pre_price = to_number(
            raw_val(q.get("preMarketPrice") or meta.get("preMarketPrice") or comp_price.get("preMarketPrice"))
        )
        post_price = to_number(
            raw_val(q.get("postMarketPrice") or meta.get("postMarketPrice") or comp_price.get("postMarketPrice"))
        )
        reg_time = to_number(meta.get("regularMarketTime"))
        pre_time = to_number(q.get("preMarketTime") or meta.get("preMarketTime"))
        post_time = to_number(q.get("postMarketTime") or meta.get("postMarketTime"))

        pre_valid = is_pre_market_fresh(pre_price, pre_time, reg_time, now_dt=now_et)
        post_valid = is_post_market_fresh(post_price, post_time, reg_time, now_dt=now_et)
        closed_post_valid = is_post_market_closed_valid(post_price, post_time, reg_time)

        if state in ("PRE", "PREPRE") and pre_valid:
            ref_close = prev_close or price
            pre_change = to_number(raw_val(meta.get("preMarketChange") or comp_price.get("preMarketChange")))
            if pre_change is None and ref_close:
                pre_change = pre_price - ref_close
            pre_change = pre_change or 0.0

            pre_pct = to_number(raw_val(meta.get("preMarketChangePercent") or comp_price.get("preMarketChangePercent")))
            if pre_pct is None and ref_close and ref_close != 0:
                pre_pct = (pre_change / ref_close) * 100
            pre_pct = pre_pct or 0.0

            sign = "+" if pre_change >= 0 else "-"
            arrow = "🔺" if pre_change > 0 else "🔻" if pre_change < 0 else "▪️"
            as_of = format_et_time(pre_time)

            lines.append(f"<b>Regular Price:</b> {p_str}")
            if prev_close:
                lines.append(f"<b>Previous Close:</b> {format_price(prev_close, curr)}")
            lines.append("")
            lines.append(f"🌅 <b>Pre-Market:</b> {format_price(pre_price, curr)}")
            lines.append(
                f"<b>Change:</b> {arrow} {sign}{format_price(abs(pre_change), curr)} ({sign}{abs(pre_pct):.2f}%)"
            )
            if as_of:
                lines.append(f"<b>As of:</b> {as_of}")
            lines.append("<b>Session:</b> Pre-market")

        elif state in ("POST", "POSTPOST") and post_valid:
            ref_close = price
            post_change = to_number(raw_val(meta.get("postMarketChange") or comp_price.get("postMarketChange")))
            if post_change is None and ref_close:
                post_change = post_price - ref_close
            post_change = post_change or 0.0

            post_pct = to_number(
                raw_val(meta.get("postMarketChangePercent") or comp_price.get("postMarketChangePercent"))
            )
            if post_pct is None and ref_close and ref_close != 0:
                post_pct = (post_change / ref_close) * 100
            post_pct = post_pct or 0.0

            sign = "+" if post_change >= 0 else "-"
            arrow = "🔺" if post_change > 0 else "🔻" if post_change < 0 else "▪️"
            as_of = format_et_time(post_time)

            lines.append(f"<b>Regular Close:</b> {p_str}")
            lines.append("")
            lines.append(f"🌙 <b>After-Hours:</b> {format_price(post_price, curr)}")
            lines.append(
                f"<b>Change:</b> {arrow} {sign}{format_price(abs(post_change), curr)} ({sign}{abs(post_pct):.2f}%)"
            )
            if as_of:
                lines.append(f"<b>As of:</b> {as_of}")
            lines.append("<b>Session:</b> After-hours")

        elif state == "REGULAR":
            lines.append(f"<b>Price:</b> {p_str}{f'  <b>Today:</b> {change}' if change else ''}")
            opening = []
            if prev_close is not None:
                opening.append(f"Prev Close {format_price(prev_close, curr)}")
            if open_val is not None:
                opening.append(f"Open {format_price(open_val, curr)}")
            if opening:
                lines.append(" · ".join(opening))
            lines.append("<b>Session:</b> Regular market")

        else:
            lines.append(f"<b>Regular Close:</b> {p_str}{f'  <b>Today:</b> {change}' if change else ''}")
            if closed_post_valid:
                post_change = to_number(raw_val(meta.get("postMarketChange") or comp_price.get("postMarketChange")))
                if post_change is None and price:
                    post_change = post_price - price
                post_change = post_change or 0.0
                post_pct = to_number(
                    raw_val(meta.get("postMarketChangePercent") or comp_price.get("postMarketChangePercent"))
                )
                if post_pct is None and price and price != 0:
                    post_pct = (post_change / price) * 100
                post_pct = post_pct or 0.0
                sign = "+" if post_change >= 0 else "-"
                as_of = format_et_time(post_time)
                lines.append(
                    f"🌙 <b>After-Hours Close:</b> {format_price(post_price, curr)} ({sign}{abs(post_pct):.2f}%)"
                    + (f" as of {as_of}" if as_of else "")
                )
            lines.append("<b>Session:</b> Closed")

    r_list = ranges(q, crypto)
    if r_list:
        lines.append(f"📊 <b>Range:</b> {' · '.join(r_list)}")

    vol = compact_number(meta.get("regularMarketVolume"))
    summary = company.get("summaryDetail") or {}
    avg_vol = compact_number(raw_val(summary.get("averageVolume") or summary.get("averageDailyVolume3Month")))
    mcap = compact_number(raw_val(comp_price.get("marketCap") or summary.get("marketCap")))

    stats = []
    if vol is not None:
        stats.append(f"Vol {vol}")
    if not crypto and avg_vol is not None:
        stats.append(f"Avg Vol {avg_vol}")
    if not crypto and mcap is not None:
        stats.append(f"Cap {'$' if curr == 'USD' else ''}{mcap}")
    if stats:
        lines.append(f"📦 {' · '.join(stats)}")

    details = [html.escape(x) for x in [meta.get("exchangeName"), curr] if x]
    reg_time = to_number(meta.get("regularMarketTime"))
    if reg_time is not None:
        try:
            dt = datetime.datetime.fromtimestamp(reg_time, datetime.timezone.utc)
            details.append(f"as of {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        except Exception:
            pass
    if details:
        lines.append(f"<i>{' · '.join(details)}</i>")

    return "\n".join(lines)


def format_compact(q: dict, label: Optional[str] = None) -> str:
    lbl = label or q["symbol"]
    crypto = q["symbol"].endswith("-USD")
    change = change_text(q, crypto)
    curr = q.get("meta", {}).get("currency")
    p_str = format_price(q["price"], curr, crypto)
    return f"<b>{html.escape(lbl)}</b>: {p_str}{f'  {change}' if change else ''}"


async def reply_for(command: str, args: list[str], message: dict, env: Any) -> Any:
    if command in ("alert", "watchlist"):
        return (
            "⚠️ <b>Notice:</b> Watchlists and price alerts have been retired.\n"
            "The bot is now a stateless financial market quote service."
        )

    if command in ("start", "help"):
        if command == "help" and args:
            name = args[0].lstrip("/").lower()
            if name in ("alert", "watchlist"):
                return (
                    f"<b>/{name}</b>\n{DIVIDER}\n"
                    "⚠️ <b>Notice:</b> Watchlists and price alerts have been retired.\n"
                    "The bot is now a stateless financial market quote service."
                )
            if name in UNAVAILABLE:
                return f"/{html.escape(name)} is unavailable in webhook mode."
            help_dict = {
                "stock": "<b>/stock &lt;ticker&gt;</b>\nQuote snapshot for a stock or ETF (with pre/post-market).",
                "crypto": "<b>/crypto &lt;symbol&gt;</b>\nQuote snapshot for a crypto pair (e.g. BTC, ETH).",
                "indices": "<b>/indices</b>\nLevels of major market indices and active U.S. futures.",
                "indicies": "<b>/indices</b>\nLevels of major market indices and active U.S. futures.",
                "search": "<b>/search &lt;query&gt;</b>\nSearch Yahoo Finance for symbols matching a name.",
                "compare": "<b>/compare &lt;t1&gt; &lt;t2&gt;</b>\nCompare 2–4 stock or crypto quotes side by side.",
                "chart": "<b>/chart &lt;ticker&gt; [1mo|3mo|6mo|1y]</b>\nClosing-price line chart PNG.",
                "stockinfo": "<b>/stockinfo &lt;ticker&gt;</b>\nCompany profile, sector, industry, and valuation.",
                "stocknews": "<b>/stocknews &lt;ticker&gt;</b>\nRecent news headlines for a stock symbol.",
                "marketcap": "<b>/marketcap &lt;ticker&gt;</b>\nCurrent market capitalization of a company.",
                "admin": "<b>/admin stats</b>\nUptime, command counts, and error stats (admin only).",
            }
            if name in help_dict:
                return help_dict[name]

        return "\n".join(
            [
                "👋 <b>Financial Market Bot</b> 📈",
                DIVIDER,
                "",
                "📈 <b>Stocks</b>",
                "📊 <b>/stock &lt;ticker&gt;</b> - Current quote with pre/post-market",
                "ℹ️ <b>/stockinfo &lt;ticker&gt;</b> - Detailed company info",
                "📰 <b>/stocknews &lt;ticker&gt;</b> - Latest news for a stock",
                "💰 <b>/marketcap &lt;ticker&gt;</b> - Market cap of a stock",
                "⚖️ <b>/compare &lt;t1&gt; &lt;t2&gt;</b> - Compare tickers",
                "📈 <b>/chart &lt;ticker&gt;</b> - Price chart PNG",
                "",
                "🪙 <b>Crypto &amp; Markets</b>",
                "🪙 <b>/crypto &lt;symbol&gt;</b> - Current price of a cryptocurrency",
                "📈 <b>/indices</b> - Major market indices and futures",
                "",
                "🔍 <b>Search</b>",
                "🔍 <b>/search &lt;query&gt;</b> - Search for a symbol",
                "",
                DIVIDER,
                "💡 Use <b>/help &lt;command&gt;</b> for more details.",
                "⚠️ <i>Disclaimer: Data is for informational purposes only.</i>",
            ]
        )

    if command == "admin":
        if not args or args[0].lower() != "stats":
            return "Usage: <code>/admin stats</code>"
        user_id = str(message.get("from", {}).get("id") or "")
        admins = parse_ids(_get_env_val(env, "ADMIN_USER_IDS"))
        if not admins or user_id not in admins:
            return "Unauthorized."
        counts = [f"  /{k}: {v}" for k, v in sorted(metrics["commands"].items())]
        lines = [
            "📊 <b>Admin Stats</b>",
            DIVIDER,
            "<b>Runtime:</b> Cloudflare Python Worker (stateless)",
            "",
            "<b>Commands</b>",
            *(counts if counts else ["  (none yet)"]),
            "",
            f"<b>Errors:</b> {metrics['errors']}",
            "<b>Provider errors</b>",
            f"  yahoo: {metrics['provider_errors']}" if metrics["provider_errors"] else "  (none)",
        ]
        return "\n".join(lines)

    if command in ("indices", "indicies"):

        async def fetch_item(sym):
            try:
                return await quote(env, sym)
            except Exception:
                return None

        cash_syms = ["^GSPC", "^DJI", "^IXIC"]
        cash_names = ["S&P 500", "Dow Jones", "Nasdaq"]
        future_syms = ["ES=F", "NQ=F", "YM=F"]
        future_names = ["S&P 500 Futures", "Nasdaq 100 Futures", "Dow Futures"]

        results = await asyncio.gather(*(fetch_item(s) for s in cash_syms + future_syms))
        cash_results = results[:3]
        future_results = results[3:]

        blocks = ["📊 <b>Major Market Indices (Cash)</b>"]
        for name, q in zip(cash_names, cash_results):
            if not q:
                blocks.append(f"🔸 <b>{html.escape(name)}</b>: Data unavailable")
            else:
                rng = ranges(q)
                rng_str = f"\n<i>{' · '.join(rng)}</i>" if rng else ""
                blocks.append(f"🔸 {format_compact(q, name)}{rng_str}")

        future_lines = []
        for name, q in zip(future_names, future_results):
            if q:
                future_lines.append(f"⚡ {format_compact(q, name)}")
        if future_lines:
            blocks.append("⚡ <b>U.S. Market Futures</b>\n" + "\n".join(future_lines))

        return f"\n{DIVIDER}\n".join(blocks)

    if command == "search":
        if not args:
            return "Please provide a search term. Example: <code>/search Vanguard</code>"
        query = " ".join(args)
        if len(query) > 64:
            return "Search query is too long. Maximum length is 64 characters."
        data = await data_request("v1/finance/search", {"q": query, "quotesCount": "8", "newsCount": "0"}, ttl=300)
        valid_types = {"EQUITY", "ETF", "CRYPTOCURRENCY", "INDEX", "MUTUALFUND", "CURRENCY"}
        quotes_raw = data.get("quotes") or []
        filtered = [x for x in quotes_raw if str(x.get("quoteType") or "").upper() in valid_types][:5]
        if not filtered:
            return f"No results found for '{html.escape(query)}'."
        lines = [f"🔍 <b>Search results for '{html.escape(query)}'</b>", DIVIDER]
        for idx, item in enumerate(filtered, start=1):
            sym = html.escape(str(item.get("symbol") or "N/A"))
            name = html.escape(str(item.get("shortname") or item.get("longname") or "N/A"))
            exch = html.escape(str(item.get("exchDisp") or item.get("exchange") or "N/A"))
            qtype = html.escape(str(item.get("typeDisp") or item.get("quoteType") or "N/A"))
            lines.append(f"<b>{idx}.</b> <code>{sym}</code> — {name} <i>({exch}, {qtype})</i>")
        first_sym = html.escape(str(filtered[0].get("symbol") or ""))
        lines.extend(["", f"💡 Try <code>/stock {first_sym}</code> for a quote."])
        return "\n".join(lines)

    if command == "stocknews":
        sym = market_symbol(args[0] if args else "")
        if not sym:
            return "Please provide a stock ticker. Example: <code>/stocknews AAPL</code>"
        data = await data_request("v1/finance/search", {"q": sym, "quotesCount": "0", "newsCount": "5"}, ttl=300)
        news = (data.get("news") or [])[:5]
        if not news:
            return f"No recent news found for {html.escape(sym)}."
        lines = [f"📰 <b>Recent news for {html.escape(sym)}</b>", DIVIDER]
        for idx, item in enumerate(news, start=1):
            title = html.escape(str(item.get("title") or "No Title"))
            link = str(item.get("link") or "")
            parsed = urllib.parse.urlparse(link)
            if parsed.scheme in ("http", "https"):
                lines.append(f'<b>{idx}.</b> <a href="{html.escape(link)}">{title}</a>')
            else:
                lines.append(f"<b>{idx}.</b> {title}")
        return "\n".join(lines)

    if command in ("stockinfo", "marketcap"):
        sym = market_symbol(args[0] if args else "")
        if not sym:
            return f"Please provide a stock ticker. Example: <code>/{command} AAPL</code>"
        company = await company_summary(sym)
        market = company.get("price") or {}
        profile = company.get("assetProfile") or {}
        details = company.get("summaryDetail") or {}
        name = market.get("shortName") or market.get("longName") or sym

        cap_val = to_number(raw_val(market.get("marketCap") or details.get("marketCap")))
        cap = "N/A" if cap_val is None else f"${compact_number(cap_val)}"
        if command == "marketcap":
            return f"💰 <b>{html.escape(name)} ({html.escape(sym)})</b>\n{DIVIDER}\nMarket Cap: <b>{cap}</b>"

        curr = market.get("currency")
        low = format_price(to_number(raw_val(details.get("fiftyTwoWeekLow"))), curr) or "N/A"
        high = format_price(to_number(raw_val(details.get("fiftyTwoWeekHigh"))), curr) or "N/A"
        pe = to_number(raw_val(details.get("trailingPE") or details.get("forwardPE")))
        div = to_number(raw_val(details.get("dividendYield")))
        summary_txt = str(profile.get("longBusinessSummary") or "No summary available.")
        website = profile.get("website")

        sec_str = html.escape(str(profile.get("sector") or "N/A"))
        ind_str = html.escape(str(profile.get("industry") or "N/A"))
        pe_str = "N/A" if pe is None else f"{pe:.2f}"
        div_str = "N/A" if div is None else f"{(div * 100):.2f}%"
        lines = [
            f"ℹ️ <b>{html.escape(name)} ({html.escape(sym)})</b>",
            DIVIDER,
            f"<b>Sector:</b> {sec_str} · <b>Industry:</b> {ind_str}",
            f"📦 Cap {cap} · P/E {pe_str} · Div {div_str} · 52W {low}–{high}",
        ]
        if website:
            parsed = urllib.parse.urlparse(str(website))
            if parsed.scheme in ("http", "https"):
                lines.append(f'<b>Website:</b> <a href="{html.escape(str(website))}">{html.escape(str(website))}</a>')
            else:
                lines.append(f"<b>Website:</b> {html.escape(str(website))}")
        shortened = re.sub(r"\s+\S*$", "", summary_txt[:400]) + "..." if len(summary_txt) > 400 else summary_txt
        lines.extend(["", "📝 <b>Summary</b>", f"<i>{html.escape(shortened)}</i>"])
        return "\n".join(lines)

    if command == "chart":
        if not args:
            return "Usage: <code>/chart AAPL</code> or <code>/chart BTC 3mo</code> (1mo, 3mo, 6mo, 1y)"
        sym = market_symbol(args[0], False, True)
        period = (args[1] if len(args) > 1 else "1mo").lower()
        if period not in ("1mo", "3mo", "6mo", "1y"):
            return "Period must be one of: <code>1mo</code>, <code>3mo</code>, <code>6mo</code>, <code>1y</code>"
        if not sym:
            return "Invalid ticker or crypto symbol format."

        data = await data_request(
            f"v8/finance/chart/{urllib.parse.quote(sym)}",
            {"range": period, "interval": "1d"},
            ttl=120,
        )
        res_list = data.get("chart", {}).get("result") or []
        res = res_list[0] if res_list else {}
        quotes = res.get("indicators", {}).get("quote") or [{}]
        values = quotes[0].get("close") or []
        timestamps = res.get("timestamp") or []

        image = render_chart(values, symbol=sym, period=period, timestamps=timestamps)
        if not image:
            return f"Could not build a chart for {html.escape(sym)}."
        return {"image": image, "caption": f"📈 {sym.replace('-USD', '/USD')} · {period}"}

    if command == "compare":
        if len(args) < 2 or len(args) > 4:
            return "Usage: <code>/compare AAPL MSFT</code>"
        symbols = [market_symbol(x, False, True) for x in args]
        if any(not s for s in symbols):
            return "One or more ticker symbols are invalid."

        async def fetch_one(s):
            try:
                return await quote(env, s)
            except Exception:
                return None

        results = await asyncio.gather(*(fetch_one(s) for s in symbols))
        lines = ["⚖️ <b>Compare</b>", DIVIDER]
        for sym, q in zip(symbols, results):
            if q:
                lines.append(format_compact(q))
            else:
                lines.append(f"<b>{html.escape(str(sym))}</b>: Data unavailable")
        return "\n".join(lines)

    if command in ("stock", "crypto"):
        sym = market_symbol(args[0] if args else "", command == "crypto")
        if not sym:
            return f"Usage: <code>/{command} &lt;symbol&gt;</code>"

        q_res = await quote(env, sym)
        return format_quote(q_res, command == "crypto")

    return None


def same_secret(actual: str, expected: str) -> bool:
    return hmac.compare_digest(actual.encode("utf-8"), expected.encode("utf-8"))


def validate_webhook_config(env: Any) -> None:
    mode = _get_env_val(env, "BOT_MODE", "webhook")
    if mode != "webhook":
        raise ValueError("BOT_MODE must be webhook")
    token = _get_env_val(env, "TELEGRAM_BOT_TOKEN")
    secret = _get_env_val(env, "TELEGRAM_WEBHOOK_SECRET")
    if not token or not re.match(r"^[A-Za-z0-9_-]{1,256}$", secret):
        raise ValueError("Telegram token and valid webhook secret are required")


async def handle_request(request: Any, env: Any) -> Response:
    req_url = str(getattr(request, "url", ""))
    parsed_url = urllib.parse.urlparse(req_url)
    path = parsed_url.path
    method = str(getattr(request, "method", "GET")).upper()

    if method == "GET" and path == "/health":
        return Response.json({"ok": True})
    if method != "POST" or path != "/webhook":
        return Response("Not found", status=404)

    try:
        validate_webhook_config(env)
    except Exception:
        return Response("Service unavailable", status=503)

    req_headers = getattr(request, "headers", {})
    if hasattr(req_headers, "get"):
        supplied = req_headers.get("X-Telegram-Bot-Api-Secret-Token", "") or req_headers.get(
            "x-telegram-bot-api-secret-token", ""
        )
        content_len = int(req_headers.get("content-length", 0) or 0)
    else:
        supplied = ""
        content_len = 0

    expected = _get_env_val(env, "TELEGRAM_WEBHOOK_SECRET")
    if not same_secret(supplied, expected):
        return Response("Forbidden", status=403)
    if content_len > 1048576:
        return Response("Too large", status=413)

    try:
        if hasattr(request, "text"):
            raw_body = await request.text()
        elif hasattr(request, "body"):
            raw_body = request.body
            if isinstance(raw_body, bytes):
                raw_body = raw_body.decode("utf-8")
        else:
            raw_body = ""
        if len(raw_body.encode("utf-8")) > 1048576:
            return Response("Too large", status=413)
        update = json.loads(raw_body)
        update_id = update.get("update_id")
        if not isinstance(update_id, int) or isinstance(update_id, bool) or update_id < 0:
            raise ValueError
    except Exception:
        return Response("Bad request", status=400)

    message = update.get("message") or update.get("edited_message")
    if not message or not isinstance(message.get("text"), str) or not (message.get("chat") or {}).get("id"):
        return Response.json({"ok": True})

    # In-memory deduplication (LRU up to 1000 items)
    if update_id in recent_updates:
        return Response.json({"ok": True, "duplicate": True})

    text_msg = message["text"]
    match = re.match(r"^/([a-zA-Z]+)(?:@([a-zA-Z0-9_]+))?(?:\s|$)", text_msg)
    if not match:
        return Response.json({"ok": True})

    try:
        bot_mention = match.group(2)
        if bot_mention:
            me = await telegram(env, "getMe")
            my_username = str(me.get("username") or "").lower()
            if bot_mention.lower() != my_username:
                return Response.json({"ok": True})

        allowed = parse_ids(_get_env_val(env, "ALLOWED_CHAT_IDS"))
        chat_id = message["chat"]["id"]
        command = match.group(1).lower()

        if allowed and "0" not in allowed and str(chat_id) not in allowed:
            reply_text = "Access denied. This bot is private."
        else:
            args_str = text_msg[match.end() :].strip()
            args = [a for a in args_str.split() if a]
            if command in KNOWN_COMMANDS:
                metrics["commands"][command] = metrics["commands"].get(command, 0) + 1
            try:
                reply_text = await reply_for(command, args, message, env)
            except Exception:
                metrics["provider_errors"] += 1
                reply_text = "Market data is unavailable right now. Please try again later."

        if isinstance(reply_text, dict) and "image" in reply_text:
            await send_photo(env, chat_id, reply_text["image"], reply_text["caption"])
        elif reply_text is not None:
            await telegram(env, "sendMessage", {"chat_id": chat_id, "text": reply_text, "parse_mode": "HTML"})

        # Record successfully processed update id
        recent_updates[update_id] = None
        if len(recent_updates) > 1000:
            recent_updates.popitem(last=False)

        return Response.json({"ok": True})
    except Exception:
        metrics["errors"] += 1
        return Response("Service unavailable", status=503)
