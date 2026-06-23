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
