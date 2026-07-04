from bot.symbols import (
    crypto_display_symbol,
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
