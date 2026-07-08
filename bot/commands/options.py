import html

GETOPTS_FLAGS = {"--getopts", "--help", "-h"}

COMMAND_ORDER = ["stock", "stockinfo", "stocknews", "marketcap", "crypto", "indices", "search"]

COMMAND_DETAILS = {
    "stock": {
        "title": "📊 <b>/stock &lt;ticker&gt;</b>",
        "summary": "Fetch a richer quote snapshot for a stock, ETF, fund, or Yahoo Finance-compatible symbol.",
        "usage": "/stock &lt;ticker&gt;",
        "examples": ["/stock AAPL", "/stock BRK.B", "/stock ^GSPC"],
        "returns": "Price, change, previous close, open, day range, 52-week range, volume, exchange, and currency.",
        "notes": "Symbols are normalized to uppercase and passed to Yahoo Finance.",
    },
    "stockinfo": {
        "title": "ℹ️ <b>/stockinfo &lt;ticker&gt;</b>",
        "summary": "Fetch company profile and fundamentals for a stock symbol.",
        "usage": "/stockinfo &lt;ticker&gt;",
        "examples": ["/stockinfo AAPL", "/stockinfo MSFT"],
        "returns": (
            "Sector, industry, country, exchange, market cap, revenue, P/E, EPS, beta, "
            "dividends, margins, website, and summary."
        ),
        "notes": "Some fundamentals may be unavailable for ETFs, funds, or thinly covered symbols.",
    },
    "stocknews": {
        "title": "📰 <b>/stocknews &lt;ticker&gt;</b>",
        "summary": "Fetch recent headlines for a stock symbol.",
        "usage": "/stocknews &lt;ticker&gt;",
        "examples": ["/stocknews AAPL", "/stocknews TSLA"],
        "returns": "Up to five headlines with links, publisher metadata, and published timestamps when available.",
        "notes": "News availability depends on Yahoo Finance coverage for the symbol.",
    },
    "marketcap": {
        "title": "💰 <b>/marketcap &lt;ticker&gt;</b>",
        "summary": "Fetch valuation details for a company.",
        "usage": "/marketcap &lt;ticker&gt;",
        "examples": ["/marketcap AAPL", "/marketcap NVDA"],
        "returns": "Market capitalization, enterprise value, shares outstanding, exchange, and currency.",
        "notes": (
            "Market cap is generally price multiplied by shares outstanding "
            "and can move throughout the trading day."
        ),
    },
    "crypto": {
        "title": "🪙 <b>/crypto &lt;symbol&gt;</b>",
        "summary": "Fetch a crypto quote from Yahoo Finance pairs.",
        "usage": "/crypto &lt;base&gt;[/&lt;quote&gt;]",
        "examples": ["/crypto BTC", "/crypto ETH/USD", "/crypto SOL-USD"],
        "returns": "Price, change, previous close, open, day range, 52-week range, volume, exchange, and currency.",
        "notes": "A bare symbol defaults to USD, so <code>/crypto BTC</code> maps to <code>BTC-USD</code>.",
    },
    "indices": {
        "title": "📈 <b>/indices</b>",
        "summary": "Fetch the configured major market indices.",
        "usage": "/indices",
        "examples": ["/indices", "/indicies"],
        "returns": "Current level, point change, percent change, previous close, day range, and market timestamp.",
        "notes": "The misspelled alias <code>/indicies</code> is supported for convenience.",
    },
    "search": {
        "title": "🔍 <b>/search &lt;query&gt;</b>",
        "summary": "Search Twelve Data for stock, ETF, crypto, index, and fund symbols.",
        "usage": "/search &lt;query&gt;",
        "examples": ["/search Apple", "/search Vanguard", "/search Bitcoin"],
        "returns": (
            "Top symbol matches with instrument name, exchange, instrument type, "
            "country, and currency when available."
        ),
        "notes": "Requires <code>TWELVEDATA_API_KEY</code> and limits queries to the configured maximum length.",
    },
}

ALIASES = {"indicies": "indices"}


def wants_getopts(args: list[str] | tuple[str, ...] | None) -> bool:
    return any(arg.lower() in GETOPTS_FLAGS for arg in args or [])


def strip_getopts(args: list[str] | tuple[str, ...] | None) -> list[str]:
    return [arg for arg in args or [] if arg.lower() not in GETOPTS_FLAGS]


def get_command_options_text(command: str) -> str:
    canonical = ALIASES.get(command.lower(), command.lower())
    details = COMMAND_DETAILS.get(canonical)
    if not details:
        return "Unknown command. Use <code>/help</code> to see the available commands."

    lines = [
        details["title"],
        details["summary"],
        "",
        f"<b>Usage:</b> <code>{details['usage']}</code>",
        f"<b>Examples:</b> {', '.join(f'<code>{example}</code>' for example in details['examples'])}",
        f"<b>Output includes:</b> {details['returns']}",
        f"<b>Notes:</b> {details['notes']}",
        "",
        "<b>Options:</b>",
        "• <code>--getopts</code>, <code>--help</code>, or <code>-h</code> — Show this command guide.",
    ]
    return "\n".join(lines)


def get_all_commands_help_text(first_name: str = "there") -> str:
    escaped_name = html.escape(first_name or "there")
    lines = [
        f"Hello {escaped_name}! I am your Financial Market Bot 📈",
        "",
        "Use these commands to look up market data:",
    ]

    for command in COMMAND_ORDER:
        details = COMMAND_DETAILS[command]
        lines.append(f"{details['title']} - {details['summary']}")

    lines.extend(
        [
            "",
            "Add <code>--getopts</code> to any command for usage, examples, output fields, and notes.",
            "Examples: <code>/stock AAPL</code>, <code>/crypto BTC</code>, <code>/stock --getopts</code>",
            "",
            "⚠️ <i>Disclaimer: Data is for informational purposes only, may be delayed, "
            "and does not constitute financial advice.</i>",
        ]
    )
    return "\n".join(lines)
