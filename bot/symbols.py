import re


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
