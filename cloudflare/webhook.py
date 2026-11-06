"""Cloudflare Python Worker webhook handler."""

import asyncio
import datetime
import decimal
import hmac
import html
import json
import math
import re
import urllib.parse
from collections import OrderedDict
from typing import Any, Optional

try:
    from chart import render_chart
    from storage import D1Storage
except ImportError:
    from cloudflare.chart import render_chart
    from cloudflare.storage import D1Storage

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


COMMANDS = "/stock /stockinfo /stocknews /marketcap /crypto /indices /search /compare /chart /watchlist /alert /admin"
KNOWN_COMMANDS = set(("start help indicies " + COMMANDS.replace("/", "")).split(" "))
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


async def timed_fetch(url: str, options: Optional[dict] = None) -> Any:
    fetcher = cf_fetch
    if fetcher is None:
        raise RuntimeError("No HTTP fetcher available in this runtime")
    opts = options or {}
    return await fetcher(url, opts)


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


async def data_request(path: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    url = f"https://query1.finance.yahoo.com/{path}?{query}"
    response = await timed_fetch(url, {"headers": {"User-Agent": "Mozilla/5.0"}})
    if getattr(response, "status", 200) >= 400:
        raise RuntimeError("Market data provider request failed")
    text = await response.text()
    return json.loads(text)


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
    data = await data_request(f"v8/finance/chart/{urllib.parse.quote(symbol)}", {"range": "5d", "interval": "1d"})
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

    current_index = -1
    regular_time = to_number(meta.get("regularMarketTime"))
    if regular_time is not None and times:
        try:
            cur_dt = datetime.datetime.fromtimestamp(regular_time, datetime.timezone.utc).strftime("%Y-%m-%d")
            for i in range(len(times) - 1, -1, -1):
                t = to_number(times[i])
                if t is not None:
                    d = datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%d")
                    if d == cur_dt:
                        current_index = i
                        break
        except Exception:
            pass

    previous = to_number(meta.get("previousClose"))
    if previous is None and current_index >= 0:
        for i in range(current_index - 1, -1, -1):
            if i < len(closes) and to_number(closes[i]) is not None:
                previous = to_number(closes[i])
                break

    lows = [to_number(x) for x in (bars.get("low") or []) if to_number(x) is not None]
    highs = [to_number(x) for x in (bars.get("high") or []) if to_number(x) is not None]

    opens = bars.get("open") or []
    open_val = to_number(opens[current_index]) if current_index >= 0 and current_index < len(opens) else None

    return {
        "symbol": symbol,
        "meta": meta,
        "price": price,
        "previous": previous,
        "open": open_val,
        "weekLow": min(lows) if lows else None,
        "weekHigh": max(highs) if highs else None,
    }


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
    add("Week", q.get("weekLow"), q.get("weekHigh"))
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


def format_quote(q: dict, crypto: bool = False) -> str:
    meta = q.get("meta") or {}
    name = meta.get("shortName") or meta.get("longName") or q["symbol"]
    display = q["symbol"].replace("-", "/") if crypto else q["symbol"]
    lines = [f"{'🪙' if crypto else '📈'} <b>{html.escape(name)} ({html.escape(display)})</b>", DIVIDER]

    change = change_text(q, crypto)
    curr = meta.get("currency")
    p_str = format_price(q["price"], curr, crypto)
    lines.append(f"<b>Price:</b> {p_str}{f'  <b>Today:</b> {change}' if change else ''}")

    company = q.get("company") or {}
    session = company.get("price") or {}
    state = str(session.get("marketState") or "").upper()
    ext_raw = (
        session.get("preMarketPrice") if state == "PRE" else session.get("postMarketPrice") if state == "POST" else None
    )
    ext_val = to_number(raw_val(ext_raw))

    if not crypto and ext_val is not None:
        raw_change = session.get("preMarketChange") if state == "PRE" else session.get("postMarketChange")
        ext_change = to_number(raw_val(raw_change))
        raw_pct = session.get("preMarketChangePercent") if state == "PRE" else session.get("postMarketChangePercent")
        ext_pct = to_number(raw_val(raw_pct))
        arrow = "" if ext_change is None else " 🔺" if ext_change > 0 else " 🔻" if ext_change < 0 else " ▪️"
        delta = "" if ext_change is None else f" {'+' if ext_change >= 0 else '-'}{format_price(abs(ext_change), curr)}"
        pct_str = "" if ext_pct is None else f" ({'+' if ext_pct >= 0 else ''}{ext_pct:.2f}%)"
        label = "Pre" if state == "PRE" else "Post"
        lines.append(
            f"{'🌅' if state == 'PRE' else '🌙'} <b>{label}:</b> {format_price(ext_val, curr)}{arrow}{delta}{pct_str}"
        )

    opening = []
    if q.get("previous") is not None:
        opening.append(f"Prev Close {format_price(q['previous'], curr, crypto)}")
    if q.get("open") is not None:
        opening.append(f"Open {format_price(q['open'], curr, crypto)}")
    if opening:
        lines.append(" · ".join(opening))

    r_list = ranges(q, crypto)
    if r_list:
        lines.append(f"📊 <b>Range:</b> {' · '.join(r_list)}")

    vol = compact_number(meta.get("regularMarketVolume"))
    summary = company.get("summaryDetail") or {}
    avg_vol = compact_number(raw_val(summary.get("averageVolume") or summary.get("averageDailyVolume3Month")))
    mcap = compact_number(raw_val(session.get("marketCap") or summary.get("marketCap")))

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
    watchlist_enabled = _get_env_val(env, "WATCHLIST_ENABLED", "false") == "true"
    alerts_enabled = _get_env_val(env, "ALERTS_ENABLED", "false") == "true"

    if command in ("start", "help"):
        if command == "help" and args:
            name = args[0].lstrip("/").lower()
            if name in UNAVAILABLE:
                return f"/{html.escape(name)} is unavailable in webhook mode."
            help_dict = {
                "stock": (
                    "<b>/stock &lt;ticker&gt;</b>\n"
                    "Shows a quote snapshot for a stock, ETF, fund, or Yahoo Finance-compatible symbol."
                ),
                "crypto": (
                    "<b>/crypto &lt;symbol&gt;</b>\n"
                    "Shows a quote snapshot for a crypto pair. Bare symbols default to USD."
                ),
                "indices": (
                    "<b>/indices</b>\n"
                    "Shows current levels and ranges of major market indices (S&amp;P 500, Dow Jones, Nasdaq)."
                ),
                "search": ("<b>/search &lt;query&gt;</b>\nSearches Yahoo Finance for a given company name or symbol."),
                "compare": (
                    "<b>/compare &lt;t1&gt; &lt;t2&gt; [t3] [t4]</b>\nCompares 2–4 stock or crypto quotes side by side."
                ),
                "chart": (
                    "<b>/chart &lt;ticker&gt; [1mo|3mo|6mo|1y]</b>\n"
                    "Renders a closing-price line chart as a PNG (default period: 1mo)."
                ),
                "stockinfo": (
                    "<b>/stockinfo &lt;ticker&gt;</b>\n"
                    "Fetches company profile information including sector, industry, description, "
                    "website, and basic valuation metrics."
                ),
                "stocknews": (
                    "<b>/stocknews &lt;ticker&gt;</b>\nFetches the latest 5 news headlines for a given stock symbol."
                ),
                "marketcap": (
                    "<b>/marketcap &lt;ticker&gt;</b>\nFetches the current market capitalization of a company."
                ),
                "watchlist": (
                    "<b>/watchlist</b> · <b>/watchlist add|remove &lt;ticker&gt;</b>\n"
                    "Personal watchlist (max 10), shared across your chats."
                ),
                "alert": (
                    "<b>/alert add &lt;ticker&gt; above|below &lt;price&gt;</b>\n"
                    "<b>/alert list</b> · <b>/alert remove &lt;id&gt;</b>\n"
                    "One-shot price alerts (max 20 per chat)."
                ),
                "admin": "<b>/admin stats</b> — owner-only usage statistics",
            }
            key = "indices" if name == "indicies" else name
            entry = help_dict.get(key)
            if entry:
                disabled = (name == "watchlist" and not watchlist_enabled) or (name == "alert" and not alerts_enabled)
                return f"{entry}\n\n<i>Currently disabled on this bot.</i>" if disabled else entry

        user_name = (message.get("from") or {}).get("first_name", "there")
        return "\n".join(
            [
                f"👋 Hello {html.escape(user_name)}! I am your Financial Market Bot 📈",
                DIVIDER,
                "",
                "📈 <b>Stocks</b>",
                "📊 <b>/stock &lt;ticker&gt;</b> - Current price of a stock",
                "ℹ️ <b>/stockinfo &lt;ticker&gt;</b> - Detailed company info",
                "📰 <b>/stocknews &lt;ticker&gt;</b> - Latest news for a stock",
                "💰 <b>/marketcap &lt;ticker&gt;</b> - Market cap of a stock",
                "⚖️ <b>/compare &lt;t1&gt; &lt;t2&gt;</b> - Compare tickers",
                (
                    f"👀 <b>/watchlist</b> - Personal watchlist (shared across chats)"
                    f"{'' if watchlist_enabled else ' — disabled'}"
                ),
                "📈 <b>/chart &lt;ticker&gt;</b> - Price chart PNG",
                f"🔔 <b>/alert</b> - One-shot price alerts (chat-owned){'' if alerts_enabled else ' — disabled'}",
                "",
                "🪙 <b>Crypto &amp; Markets</b>",
                "🪙 <b>/crypto &lt;symbol&gt;</b> - Current price of a cryptocurrency",
                "📈 <b>/indices</b> - Levels of major market indices",
                "",
                "🔍 <b>Search</b>",
                "🔍 <b>/search &lt;query&gt;</b> - Search for a symbol",
                "",
                DIVIDER,
                "💡 For more info on a command, use <b>/help &lt;command&gt;</b> (e.g., <code>/help stock</code>)",
                "",
                (
                    "⚠️ <i>Disclaimer: Data is for informational purposes only, may be delayed, "
                    "and does not constitute financial advice.</i>"
                ),
            ]
        )

    if command in UNAVAILABLE:
        return f"/{command} is unavailable in webhook mode."

    if command == "watchlist":
        if not watchlist_enabled:
            return "Watchlists are disabled on this bot."
        from_user = message.get("from") or {}
        user_id = from_user.get("id")
        if not user_id:
            return "Watchlists are personal and need your Telegram user identity."

        db = getattr(env, "DB", None) or (env.get("DB") if isinstance(env, dict) else None)
        storage = D1Storage(db)
        if not args:
            symbols = await storage.watchlist(user_id)
            if not symbols:
                return "Your watchlist is empty. Add one with <code>/watchlist add AAPL</code>"

            async def get_quote_safe(sym):
                try:
                    return await quote(env, sym)
                except Exception:
                    return None

            quotes = await asyncio.gather(*(get_quote_safe(s) for s in symbols))
            lines = ["👀 <b>Your Watchlist</b>", DIVIDER]
            for sym, q in zip(symbols, quotes):
                if q:
                    lines.append(format_compact(q, sym.replace("-USD", "/USD")))
                else:
                    lines.append(f"<b>{html.escape(sym)}</b>: Data unavailable")
            return "\n".join(lines)

        action = args[0].lower()
        if action in ("add", "remove", "rm", "del", "delete"):
            if len(args) < 2:
                return f"Usage: <code>/watchlist {html.escape(action)} TICKER</code>"
            sym = market_symbol(args[1], False, True)
            if not sym:
                return "Invalid ticker or crypto symbol format."
            ok, msg = (
                await storage.add_watchlist(user_id, sym)
                if action == "add"
                else await storage.remove_watchlist(user_id, sym)
            )
            icon = "✅" if ok else "⚠️"
            return f"{icon} {html.escape(msg)}"

        return (
            "Usage:\n<code>/watchlist</code> — show quotes\n"
            "<code>/watchlist add AAPL</code>\n<code>/watchlist remove AAPL</code>"
        )

    if command == "alert":
        if not alerts_enabled:
            return "Price alerts are disabled on this bot."
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        from_user = message.get("from") or {}
        user_id = from_user.get("id")
        db = getattr(env, "DB", None) or (env.get("DB") if isinstance(env, dict) else None)
        storage = D1Storage(db)
        action = (args[0] if args else "list").lower()

        if action in ("list", "ls"):
            rows = await storage.alerts(chat_id)
            if not rows:
                return "No alerts. Create one with <code>/alert add AAPL above 200</code>"
            lines = ["🔔 <b>Alerts</b>", DIVIDER]
            for row in rows:
                r_id = row["id"] if isinstance(row, dict) else getattr(row, "id", None)
                r_sym = row["symbol"] if isinstance(row, dict) else getattr(row, "symbol", None)
                r_dir = row["direction"] if isinstance(row, dict) else getattr(row, "direction", None)
                r_thr = row["threshold"] if isinstance(row, dict) else getattr(row, "threshold", None)
                lines.append(f"<b>#{r_id}</b> {html.escape(str(r_sym))} {html.escape(str(r_dir))} {r_thr}")
            lines.extend(["", "Remove with <code>/alert remove ID</code>"])
            return "\n".join(lines)

        if action == "add":
            if len(args) < 4:
                return "Usage: <code>/alert add AAPL above 200</code> or <code>/alert add BTC above 100000</code>"
            sym = market_symbol(args[1], False, True)
            if not sym:
                return "Invalid ticker or crypto symbol format."
            direction = args[2].lower()
            if direction not in ("above", "below"):
                return "Direction must be <code>above</code> or <code>below</code>."
            try:
                threshold = float(args[3].replace("$", "").replace(",", ""))
                if not math.isfinite(threshold):
                    raise ValueError
            except ValueError:
                return "Price must be a number."
            if not user_id:
                return "Alerts need your Telegram user identity."

            ok, msg = await storage.add_alert(chat_id, user_id, sym, direction, threshold)
            icon = "✅" if ok else "⚠️"
            return f"{icon} {html.escape(msg)}"

        if action in ("remove", "rm", "del", "delete"):
            if len(args) < 2:
                return "Usage: <code>/alert remove 3</code>"
            try:
                alert_id = int(args[1].lstrip("#"))
                if alert_id <= 0:
                    raise ValueError
            except ValueError:
                return "Alert ID must be a number."
            ok, msg = await storage.remove_alert(chat_id, alert_id)
            icon = "✅" if ok else "⚠️"
            return f"{icon} {html.escape(msg)}"

        return "Usage:\n<code>/alert add AAPL above 200</code>\n<code>/alert list</code>\n<code>/alert remove 3</code>"

    if command == "admin":
        admin_ids = parse_ids(_get_env_val(env, "ADMIN_USER_IDS"))
        from_user = message.get("from") or {}
        if str(from_user.get("id")) not in admin_ids:
            return "Access denied."
        if args and args[0].lower() not in ("stats", "status", "metrics"):
            return "Usage: <code>/admin stats</code>"
        counts = [f"  {html.escape(k)}: {v}" for k, v in sorted(metrics["commands"].items())]
        lines = [
            "📊 <b>Admin stats</b>",
            DIVIDER,
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

        async def fetch_idx(sym):
            try:
                return await quote(env, sym)
            except Exception:
                return None

        results = await asyncio.gather(*(fetch_idx(s) for s in ["^GSPC", "^DJI", "^IXIC"]))
        blocks = ["📊 <b>Major Market Indices</b>"]
        names = ["S&P 500", "Dow Jones", "Nasdaq"]
        for name, q in zip(names, results):
            if not q:
                blocks.append(f"🔸 <b>{html.escape(name)}</b>: Data unavailable")
            else:
                rng = ranges(q)
                rng_str = f"\n<i>{' · '.join(rng)}</i>" if rng else ""
                blocks.append(f"🔸 {format_compact(q, name)}{rng_str}")
        return f"\n{DIVIDER}\n".join(blocks)

    if command == "search":
        if not args:
            return "Please provide a search term. Example: <code>/search Vanguard</code>"
        query = " ".join(args)
        if len(query) > 64:
            return "Search query is too long. Maximum length is 64 characters."
        data = await data_request("v1/finance/search", {"q": query, "quotesCount": "8", "newsCount": "0"})
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
        data = await data_request("v1/finance/search", {"q": sym, "quotesCount": "0", "newsCount": "5"})
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

        data = await data_request(f"v8/finance/chart/{urllib.parse.quote(sym)}", {"range": period, "interval": "1d"})
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
            return "Invalid ticker or crypto symbol format."

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

        async def get_summary():
            if command == "stock":
                try:
                    return await company_summary(sym)
                except Exception:
                    return None
            return None

        q_res, comp = await asyncio.gather(quote(env, sym), get_summary())
        if comp:
            q_res["company"] = comp
        return format_quote(q_res, command == "crypto")

    return None


def same_secret(actual: str, expected: str) -> bool:
    return hmac.compare_digest(actual.encode("utf-8"), expected.encode("utf-8"))


def validate_webhook_config(env: Any) -> None:
    mode = _get_env_val(env, "BOT_MODE")
    if mode != "webhook":
        raise ValueError("BOT_MODE must be webhook")
    token = _get_env_val(env, "TELEGRAM_BOT_TOKEN")
    secret = _get_env_val(env, "TELEGRAM_WEBHOOK_SECRET")
    if not token or not re.match(r"^[A-Za-z0-9_-]{1,256}$", secret):
        raise ValueError("Telegram token and valid webhook secret are required")

    watchlists = _get_env_val(env, "WATCHLIST_ENABLED", "false")
    alerts = _get_env_val(env, "ALERTS_ENABLED", "false")
    if watchlists not in ("true", "false") or alerts not in ("true", "false"):
        raise ValueError("Feature flags must be true or false")

    backend = _get_env_val(env, "STORAGE_BACKEND", "none")
    if backend not in ("none", "d1"):
        raise ValueError("Cloudflare Workers only supports none or d1 storage backend")

    db = getattr(env, "DB", None) or (env.get("DB") if isinstance(env, dict) else None)
    if backend == "d1" and not db:
        raise ValueError("D1 storage backend requires a DB binding")
    if (watchlists == "true" or alerts == "true") and (backend != "d1" or not db):
        raise ValueError("Enabled watchlists or alerts require persistent storage (d1) and a DB binding")


async def check_alerts(env: Any) -> None:
    validate_webhook_config(env)
    if _get_env_val(env, "ALERTS_ENABLED", "false") != "true":
        return
    db = getattr(env, "DB", None) or (env.get("DB") if isinstance(env, dict) else None)
    storage = D1Storage(db)
    rows = await storage.all_alerts()
    prices: dict[str, Any] = {}

    for row in rows:
        r_id = row["id"] if isinstance(row, dict) else getattr(row, "id", None)
        r_chat = row["chat_id"] if isinstance(row, dict) else getattr(row, "chat_id", None)
        r_sym = row["symbol"] if isinstance(row, dict) else getattr(row, "symbol", None)
        r_dir = row["direction"] if isinstance(row, dict) else getattr(row, "direction", None)
        r_thr = row["threshold"] if isinstance(row, dict) else getattr(row, "threshold", None)

        if r_sym not in prices:
            try:
                prices[r_sym] = await quote(env, r_sym)
            except Exception:
                prices[r_sym] = None

        q = prices[r_sym]
        if not q:
            continue
        curr_price = q["price"]
        condition = curr_price >= r_thr if r_dir == "above" else curr_price <= r_thr
        if not condition:
            continue

        if not await storage.claim_alert(r_id):
            continue

        try:
            p_str = format_price(curr_price, q.get("meta", {}).get("currency"), r_sym.endswith("-USD"))
            text = f"🔔 <b>Alert #{r_id}</b>\n{html.escape(r_sym)} is {p_str} ({html.escape(r_dir)} {r_thr})"
            await telegram(env, "sendMessage", {"chat_id": r_chat, "text": text, "parse_mode": "HTML"})
            await storage.finish_alert(r_id)
        except Exception:
            await storage.release_alert(r_id)


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

    # Duplicate suppression
    backend = _get_env_val(env, "STORAGE_BACKEND", "none")
    db = getattr(env, "DB", None) or (env.get("DB") if isinstance(env, dict) else None)
    if backend == "d1" and db:
        storage = D1Storage(db)
        is_new = await storage.claim_update(update_id)
        if not is_new:
            return Response.json({"ok": True, "duplicate": True})
    else:
        if update_id in recent_updates:
            return Response.json({"ok": True, "duplicate": True})
        recent_updates[update_id] = None
        if len(recent_updates) > 10000:
            recent_updates.popitem(last=False)

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
                if command in ("watchlist", "alert"):
                    metrics["errors"] += 1
                    reply_text = "Storage is unavailable right now. Please try again later."
                else:
                    metrics["provider_errors"] += 1
                    reply_text = "Market data is unavailable right now. Please try again later."

        if isinstance(reply_text, dict) and "image" in reply_text:
            await send_photo(env, chat_id, reply_text["image"], reply_text["caption"])
        elif reply_text is not None:
            await telegram(env, "sendMessage", {"chat_id": chat_id, "text": reply_text, "parse_mode": "HTML"})
        return Response.json({"ok": True})
    except Exception:
        metrics["errors"] += 1
        return Response("Service unavailable", status=503)
