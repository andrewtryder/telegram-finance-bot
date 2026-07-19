import re

# Quote currencies that mark a hyphenated pair as crypto (e.g. BTC-USD, ETH-USDT).
KNOWN_CRYPTO_QUOTES = frozenset({"USD", "USDT", "EUR", "GBP", "BTC", "ETH"})

# Bare bases that should resolve to BASE-USD (avoid equity collisions like COIN).
COMMON_CRYPTO_BASES = frozenset(
    {
        "BTC",
        "ETH",
        "SOL",
        "XRP",
        "DOGE",
        "ADA",
        "AVAX",
        "DOT",
        "LINK",
        "ATOM",
        "LTC",
        "BCH",
        "UNI",
        "AAVE",
        "PEPE",
        "SHIB",
        "TON",
        "TRX",
        "NEAR",
        "APT",
        "SUI",
        "SEI",
        "ARB",
        "OP",
        "FIL",
        "ICP",
        "HBAR",
        "ALGO",
        "XLM",
        "VET",
        "XMR",
        "ETC",
    }
)


def to_yfinance_stock(ticker: str) -> str:
    return ticker.strip().upper()


def to_yfinance_crypto(symbol: str) -> str:
    normalized = symbol.strip().upper().replace("/", "-")
    if "-" not in normalized:
        normalized = f"{normalized}-USD"
    return normalized


def crypto_display_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if "/" in normalized:
        return normalized
    if "-" in normalized:
        base, quote = normalized.split("-", 1)
        return f"{base}/{quote}"
    return f"{normalized}/USD"


# Central validation rules
# Stocks: up to 16 alphanumeric characters, dots, dashes, equal signs, or caret (e.g. ^GSPC, BRK.B, AAPL)
STOCK_RE = re.compile(r"^[A-Z0-9^][A-Z0-9.\-=^]{0,15}$")
# Crypto: up to 15 alphanumeric characters base, optionally followed by / or -
# and up to 15 alphanumeric characters quote
CRYPTO_RE = re.compile(r"^[A-Z0-9]{1,15}([/-][A-Z0-9]{1,15})?$")


def validate_stock_ticker(ticker: str) -> bool:
    return bool(STOCK_RE.match(ticker.strip().upper()))


def validate_crypto_symbol(symbol: str) -> bool:
    return bool(CRYPTO_RE.match(symbol.strip().upper()))


def is_crypto_symbol(yf_symbol: str) -> bool:
    """True when a stored/normalized Yahoo symbol looks like a crypto pair."""
    normalized = yf_symbol.strip().upper()
    if "-" not in normalized:
        return normalized in COMMON_CRYPTO_BASES
    _base, quote = normalized.split("-", 1)
    return quote in KNOWN_CRYPTO_QUOTES


def _looks_like_crypto_input(raw: str) -> bool:
    upper = raw.strip().upper()
    if "/" in upper:
        return validate_crypto_symbol(upper)
    if "-" in upper:
        if not validate_crypto_symbol(upper):
            return False
        _base, quote = upper.replace("/", "-").split("-", 1)
        return quote in KNOWN_CRYPTO_QUOTES
    return upper in COMMON_CRYPTO_BASES and validate_crypto_symbol(upper)


def resolve_market_symbol(raw: str) -> tuple[str, str, bool] | None:
    """Resolve user input to (yfinance_symbol, display_symbol, is_crypto).

    Crypto when: slash pair, hyphen + known quote currency, or bare common crypto base.
    Otherwise stock. Returns None if the input is invalid for both paths.
    """
    if not raw or not raw.strip():
        return None

    if _looks_like_crypto_input(raw):
        if not validate_crypto_symbol(raw):
            return None
        yf_symbol = to_yfinance_crypto(raw)
        return yf_symbol, crypto_display_symbol(raw), True

    if validate_stock_ticker(raw):
        yf_symbol = to_yfinance_stock(raw)
        return yf_symbol, yf_symbol, False

    return None
