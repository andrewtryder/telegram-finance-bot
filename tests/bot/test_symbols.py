from bot.symbols import to_yfinance_stock, to_yfinance_crypto, crypto_display_symbol

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
