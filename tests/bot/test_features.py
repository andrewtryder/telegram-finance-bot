from bot.chart import render_chart
from bot.metrics import record_command, record_error, reset, snapshot
from bot.symbols import is_crypto_symbol, to_yfinance_crypto, to_yfinance_stock


def test_metrics_snapshot():
    reset()
    record_command("stock")
    record_command("stock")
    record_error()
    snap = snapshot()
    assert snap["commands_total"]["stock"] == 2
    assert snap["errors_total"] == 1


def test_symbols_conversion():
    assert to_yfinance_stock("AAPL") == "AAPL"
    assert to_yfinance_crypto("BTC") == "BTC-USD"
    assert to_yfinance_crypto("BTC/USD") == "BTC-USD"
    assert is_crypto_symbol("BTC-USD") is True
    assert is_crypto_symbol("AAPL") is False


def test_stateless_chart_rendering():
    prices = [150.0, 152.5, 151.0, 154.0, 153.5]
    png = render_chart(prices, symbol="AAPL", period="1MO", timestamps=[1700000000 + i * 86400 for i in range(5)])
    assert isinstance(png, bytes)
    assert png.startswith(b"\x89PNG")
    assert len(png) > 1000
