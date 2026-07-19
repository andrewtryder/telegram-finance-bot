from bot.symbols import (
    crypto_display_symbol,
    is_crypto_symbol,
    resolve_market_symbol,
    to_yfinance_crypto,
    to_yfinance_stock,
    validate_crypto_symbol,
    validate_stock_ticker,
)


def test_to_yfinance_stock():
    assert to_yfinance_stock("aapl") == "AAPL"
    assert to_yfinance_stock(" AAPL ") == "AAPL"


def test_to_yfinance_crypto():
    assert to_yfinance_crypto("btc") == "BTC-USD"
    assert to_yfinance_crypto("eth/usd") == "ETH-USD"
    assert to_yfinance_crypto("doge-usd") == "DOGE-USD"
    assert to_yfinance_crypto("  BTC  ") == "BTC-USD"
    assert to_yfinance_crypto("MATIC/BTC") == "MATIC-BTC"


def test_crypto_display_symbol():
    assert crypto_display_symbol("btc") == "BTC/USD"
    assert crypto_display_symbol("eth/usd") == "ETH/USD"
    assert crypto_display_symbol("doge-usd") == "DOGE/USD"
    assert crypto_display_symbol("MATIC/BTC") == "MATIC/BTC"


def test_validate_stock_ticker():
    assert validate_stock_ticker("AAPL") is True
    assert validate_stock_ticker("BRK.B") is True
    assert validate_stock_ticker("^GSPC") is True
    assert validate_stock_ticker("A" * 17) is False
    assert validate_stock_ticker("AAPL_*[]()") is False


def test_validate_crypto_symbol():
    assert validate_crypto_symbol("BTC") is True
    assert validate_crypto_symbol("BTC/USD") is True
    assert validate_crypto_symbol("ETH-USD") is True
    assert validate_crypto_symbol("BTC_USD") is False


def test_resolve_market_symbol_crypto():
    assert resolve_market_symbol("BTC") == ("BTC-USD", "BTC/USD", True)
    assert resolve_market_symbol("btc/usd") == ("BTC-USD", "BTC/USD", True)
    assert resolve_market_symbol("ETH-USD") == ("ETH-USD", "ETH/USD", True)
    assert resolve_market_symbol("doge") == ("DOGE-USD", "DOGE/USD", True)


def test_resolve_market_symbol_stock():
    assert resolve_market_symbol("AAPL") == ("AAPL", "AAPL", False)
    assert resolve_market_symbol("BRK.B") == ("BRK.B", "BRK.B", False)
    # Equity ticker that must not be treated as crypto bare base
    assert resolve_market_symbol("COIN") == ("COIN", "COIN", False)


def test_resolve_market_symbol_invalid():
    assert resolve_market_symbol("") is None
    assert resolve_market_symbol("BAD$") is None
    assert resolve_market_symbol("AAPL_*") is None


def test_is_crypto_symbol():
    assert is_crypto_symbol("BTC-USD") is True
    assert is_crypto_symbol("ETH-USDT") is True
    assert is_crypto_symbol("AAPL") is False
    assert is_crypto_symbol("COIN") is False
