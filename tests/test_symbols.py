import pytest
from symbols import to_yfinance_stock, to_yfinance_crypto, crypto_display_symbol


def test_to_yfinance_stock():
    assert to_yfinance_stock("aapl") == "AAPL"
    assert to_yfinance_stock("  msft  ") == "MSFT"


def test_to_yfinance_crypto():
    assert to_yfinance_crypto("BTC") == "BTC-USD"
    assert to_yfinance_crypto("BTC/USD") == "BTC-USD"
    assert to_yfinance_crypto("btc-usd") == "BTC-USD"
    assert to_yfinance_crypto("ETH-EUR") == "ETH-EUR"


def test_crypto_display_symbol():
    assert crypto_display_symbol("BTC") == "BTC/USD"
    assert crypto_display_symbol("BTC/USD") == "BTC/USD"
    assert crypto_display_symbol("BTC-USD") == "BTC/USD"
    assert crypto_display_symbol("ETH-EUR") == "ETH/EUR"
