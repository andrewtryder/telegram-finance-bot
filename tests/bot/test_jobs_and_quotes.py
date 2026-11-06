"""Tests for quote formatting, extended hours (pre/post-market), and session labeling."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from bot.metrics import record_provider_error, reset, snapshot
from bot.services import (
    EASTERN_TZ,
    _format_price,
    format_compact_quote,
    format_et_time,
    get_quote_formatted,
)


@pytest.fixture(autouse=True)
def _reset_metrics():
    reset()
    yield
    reset()


def test_format_price_crypto_sub_dollar():
    assert _format_price(0.1234, True) == "$0.1234"
    assert _format_price(1.5, True) == "$1.50"
    assert _format_price(0.1234, False) == "$0.12"
    assert _format_price(None, False) == "N/A"
    assert _format_price("invalid", False) == "N/A"


def test_format_et_time():
    # 1700000000 is 2023-11-14 22:13:20 UTC -> 17:13:20 EST -> 5:13 PM ET
    formatted = format_et_time(1700000000)
    assert formatted.endswith("ET")
    assert ":" in formatted
    assert "AM" in formatted or "PM" in formatted
    assert format_et_time(None) == ""


def test_format_compact_quote_up():
    line = format_compact_quote(
        {"regularMarketPrice": 110.0, "previousClose": 100.0},
        "AAPL",
    )
    assert "AAPL" in line
    assert "$110.00" in line
    assert "+10.00" in line
    assert "(+10.00%)" in line


def test_format_compact_quote_crypto_sub_dollar():
    line = format_compact_quote(
        {"regularMarketPrice": 0.0842, "previousClose": 0.0800},
        "DOGE/USD",
        is_crypto=True,
    )
    assert "DOGE/USD" in line
    assert "$0.0842" in line
    assert "+0.0042" in line


def test_format_compact_quote_missing_prev_close():
    line = format_compact_quote(
        {"regularMarketPrice": 50.0, "regularMarketChange": 1.25, "regularMarketChangePercent": 2.56},
        "XYZ",
    )
    assert "XYZ" in line
    assert "$50.00" in line
    assert "+1.25" in line
    assert "(+2.56%)" in line


@pytest.mark.asyncio
async def test_get_quote_formatted_pre_market():
    ref_now = datetime(2026, 11, 10, 8, 30, tzinfo=EASTERN_TZ)
    pre_time = int(datetime(2026, 11, 10, 8, 15, tzinfo=EASTERN_TZ).timestamp())
    reg_time = int(datetime(2026, 11, 9, 16, 0, tzinfo=EASTERN_TZ).timestamp())
    mock_data = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 250.0,
        "previousClose": 248.5,
        "marketState": "PRE",
        "preMarketPrice": 252.15,
        "preMarketChange": 3.65,
        "preMarketChangePercent": 1.47,
        "regularMarketTime": reg_time,
        "preMarketTime": pre_time,
    }
    with patch("bot.services._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = mock_data
        result = await get_quote_formatted("AAPL", now_dt=ref_now)

    assert "Apple Inc. (AAPL)" in result
    assert "Regular Price:</b> $250.00" in result
    assert "Previous Close:</b> $248.50" in result
    assert "🌅 <b>Pre-Market:</b> $252.15" in result
    assert "+3.65" in result
    assert "(+1.47%)" in result
    assert "Session:</b> Pre-market" in result
    assert "Nov 10, 8:15 AM ET" in result


@pytest.mark.asyncio
async def test_get_quote_formatted_after_hours():
    ref_now = datetime(2026, 11, 10, 17, 30, tzinfo=EASTERN_TZ)
    reg_time = int(datetime(2026, 11, 10, 16, 0, tzinfo=EASTERN_TZ).timestamp())
    post_time = int(datetime(2026, 11, 10, 17, 15, tzinfo=EASTERN_TZ).timestamp())
    mock_data = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 250.0,
        "previousClose": 248.5,
        "marketState": "POST",
        "postMarketPrice": 251.25,
        "postMarketChange": 1.25,
        "postMarketChangePercent": 0.50,
        "regularMarketTime": reg_time,
        "postMarketTime": post_time,
    }
    with patch("bot.services._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = mock_data
        result = await get_quote_formatted("AAPL", now_dt=ref_now)

    assert "Apple Inc. (AAPL)" in result
    assert "Regular Close:</b> $250.00" in result
    assert "🌙 <b>After-Hours:</b> $251.25" in result
    assert "+1.25" in result
    assert "(+0.50%)" in result
    assert "Session:</b> After-hours" in result
    assert "Nov 10, 5:15 PM ET" in result


@pytest.mark.asyncio
async def test_get_quote_formatted_regular_session():
    mock_data = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 250.0,
        "previousClose": 248.5,
        "open": 249.0,
        "marketState": "REGULAR",
        "dayHigh": 251.0,
        "dayLow": 248.0,
    }
    with patch("bot.services._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = mock_data
        result = await get_quote_formatted("AAPL")

    assert "Apple Inc. (AAPL)" in result
    assert "Price:</b> $250.00" in result
    assert "Prev Close $248.50" in result
    assert "Open $249.00" in result
    assert "Session:</b> Regular market" in result
    assert "Pre-Market" not in result
    assert "After-Hours" not in result


@pytest.mark.asyncio
async def test_get_quote_formatted_crypto():
    mock_data = {
        "shortName": "Bitcoin USD",
        "regularMarketPrice": 65432.10,
        "previousClose": 64000.0,
        "marketState": "REGULAR",
    }
    with patch("bot.services._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = mock_data
        result = await get_quote_formatted("BTC-USD", display_symbol="BTC", is_crypto=True)

    assert "🪙 <b>Bitcoin USD (BTC)</b>" in result
    assert "$65,432.10" in result
    assert "24/7 continuous trading" in result
    assert "Pre-Market" not in result
    assert "After-Hours" not in result


@pytest.mark.asyncio
async def test_get_quote_formatted_cash_index():
    mock_data = {
        "shortName": "S&P 500",
        "regularMarketPrice": 5000.0,
        "previousClose": 4950.0,
        "marketState": "POST",
        "postMarketPrice": 5010.0,  # Cash indices do not have extended hours trades
    }
    with patch("bot.services._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = mock_data
        result = await get_quote_formatted("^GSPC", display_symbol="S&P 500", is_crypto=False)

    assert "S&amp;P 500" in result
    assert "Regular cash index" in result
    assert "Pre-Market" not in result
    assert "After-Hours" not in result


@pytest.mark.asyncio
async def test_get_quote_formatted_stale_pre_market_not_displayed():
    # If regular session traded after pre-market, pre-market quote is stale and must not be shown as active
    mock_data = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 250.0,
        "previousClose": 248.5,
        "marketState": "REGULAR",
        "preMarketPrice": 247.0,
        "preMarketTime": 1700000000,
        "regularMarketTime": 1700005000,
    }
    with patch("bot.services._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = mock_data
        result = await get_quote_formatted("AAPL")

    assert "Session:</b> Regular market" in result
    assert "Pre-Market:" not in result


@pytest.mark.asyncio
async def test_get_quote_formatted_missing_or_zero_prev_close():
    mock_data = {
        "shortName": "IPO Corp",
        "regularMarketPrice": 15.0,
        "previousClose": 0.0,
        "regularMarketChange": 1.5,
        "regularMarketChangePercent": 11.11,
        "marketState": "REGULAR",
    }
    with patch("bot.services._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = mock_data
        result = await get_quote_formatted("IPOC")

    assert "IPO Corp" in result
    assert "$15.00" in result
    assert "+$1.50" in result
    assert "(+11.11%)" in result


@pytest.mark.asyncio
async def test_get_quote_formatted_closed_market_with_post_trade():
    mock_data = {
        "shortName": "Tesla Inc.",
        "regularMarketPrice": 200.0,
        "previousClose": 195.0,
        "marketState": "CLOSED",
        "postMarketPrice": 205.0,
        "postMarketChange": 5.0,
        "postMarketChangePercent": 2.5,
        "regularMarketTime": 1700000000,
        "postMarketTime": 1700005000,
    }
    with patch("bot.services._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = mock_data
        result = await get_quote_formatted("TSLA")

    assert "Session:</b> Closed" in result
    assert "🌙 <b>After-Hours Close:</b> $205.00 (+2.50%)" in result


def test_format_et_time_daylight_saving():
    # Summer (July 1, 2024 16:00 UTC -> 12:00 PM EDT)
    summer_epoch = 1719849600
    assert format_et_time(summer_epoch) == "Jul 1, 12:00 PM ET"

    # Winter (Jan 1, 2024 17:00 UTC -> 12:00 PM EST)
    winter_epoch = 1704128400
    assert format_et_time(winter_epoch) == "Jan 1, 12:00 PM ET"


def test_metrics_provider_error():
    record_provider_error("yahoo")
    snap = snapshot()
    assert snap["provider_errors"]["yahoo"] == 1


@pytest.mark.asyncio
async def test_pre_market_missing_timestamp_rejected():
    # If preMarketTime is missing/None, pre-market quote must be rejected as stale/unverified
    ref_now = datetime(2026, 11, 10, 8, 30, tzinfo=EASTERN_TZ)
    mock_data = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 250.0,
        "previousClose": 248.5,
        "marketState": "PRE",
        "preMarketPrice": 252.15,
        "preMarketChange": 3.65,
        "preMarketChangePercent": 1.47,
        "regularMarketTime": int(datetime(2026, 11, 9, 16, 0, tzinfo=EASTERN_TZ).timestamp()),
        "preMarketTime": None,  # Missing timestamp
    }
    with patch("bot.services._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = mock_data
        result = await get_quote_formatted("AAPL", now_dt=ref_now)

    assert "Session:</b> Closed" in result
    assert "🌅 <b>Pre-Market:</b>" not in result


@pytest.mark.asyncio
async def test_pre_market_friday_timestamp_on_monday_rejected():
    # On Monday morning, a Friday pre-market trade timestamp must be rejected
    monday_morning = datetime(2026, 11, 9, 8, 30, tzinfo=EASTERN_TZ)  # Monday Nov 9
    friday_pre_time = int(datetime(2026, 11, 6, 8, 15, tzinfo=EASTERN_TZ).timestamp())  # Friday Nov 6
    friday_reg_time = int(datetime(2026, 11, 6, 16, 0, tzinfo=EASTERN_TZ).timestamp())

    mock_data = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 250.0,
        "previousClose": 248.5,
        "marketState": "PRE",  # Provider still reports PRE
        "preMarketPrice": 252.15,
        "preMarketChange": 3.65,
        "preMarketChangePercent": 1.47,
        "regularMarketTime": friday_reg_time,
        "preMarketTime": friday_pre_time,  # Old Friday pre-market trade
    }
    with patch("bot.services._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = mock_data
        result = await get_quote_formatted("AAPL", now_dt=monday_morning)

    assert "Session:</b> Closed" in result
    assert "🌅 <b>Pre-Market:</b>" not in result


@pytest.mark.asyncio
async def test_pre_market_weekend_rejected():
    # On Saturday, active pre-market must not be shown even if marketState says PRE
    saturday = datetime(2026, 11, 7, 8, 30, tzinfo=EASTERN_TZ)
    pre_time = int(datetime(2026, 11, 7, 8, 15, tzinfo=EASTERN_TZ).timestamp())
    mock_data = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 250.0,
        "previousClose": 248.5,
        "marketState": "PRE",
        "preMarketPrice": 252.15,
        "preMarketTime": pre_time,
    }
    with patch("bot.services._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = mock_data
        result = await get_quote_formatted("AAPL", now_dt=saturday)

    assert "Session:</b> Closed" in result
    assert "🌅 <b>Pre-Market:</b>" not in result


@pytest.mark.asyncio
async def test_post_market_missing_timestamp_rejected():
    # If postMarketTime is missing/None, after-hours quote must not be shown as active
    ref_now = datetime(2026, 11, 10, 17, 30, tzinfo=EASTERN_TZ)
    mock_data = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 250.0,
        "previousClose": 248.5,
        "marketState": "POST",
        "postMarketPrice": 251.25,
        "regularMarketTime": int(datetime(2026, 11, 10, 16, 0, tzinfo=EASTERN_TZ).timestamp()),
        "postMarketTime": None,
    }
    with patch("bot.services._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = mock_data
        result = await get_quote_formatted("AAPL", now_dt=ref_now)

    assert "Session:</b> Closed" in result
    assert "🌙 <b>After-Hours:</b>" not in result
