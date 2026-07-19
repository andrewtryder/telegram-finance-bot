import time
from unittest.mock import AsyncMock, patch

import pytest

from bot import config
from bot import services as main


@pytest.fixture(autouse=True)
def clear_cache_and_reset():
    main.QUOTE_CACHE.clear()
    main.SEARCH_CACHE.clear()
    config.PROVIDER_TIMEOUT = 10.0
    config.INITIAL_BACKOFF = 0.5


@pytest.mark.asyncio
@patch("bot.services.asyncio.to_thread", new_callable=AsyncMock)
async def test_get_quote_formatted_success(mock_to_thread):
    mock_to_thread.return_value = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 150.50,
        "regularMarketChange": 1.50,
        "regularMarketChangePercent": 1.00,
        "regularMarketTime": 1672531200,
    }

    result = await main.get_quote_formatted("AAPL")
    assert "<b>Price:</b> $150.50" in result
    assert "📈 <b>Apple Inc. (AAPL)</b>" in result
    assert "<b>Today:</b>" in result


@pytest.mark.asyncio
@patch("bot.services.asyncio.to_thread", new_callable=AsyncMock)
async def test_get_quote_formatted_missing_price(mock_to_thread):
    mock_to_thread.return_value = {"shortName": "Invalid"}

    result = await main.get_quote_formatted("INVALID")
    assert "Could not fetch current price for <b>INVALID</b>" in result


@pytest.mark.asyncio
@patch("bot.services.asyncio.to_thread", new_callable=AsyncMock)
async def test_get_quote_formatted_exception(mock_to_thread):
    mock_to_thread.side_effect = Exception("Network error")
    config.INITIAL_BACKOFF = 0.001

    result = await main.get_quote_formatted("AAPL")
    assert "Sorry, I encountered an error fetching data for <b>AAPL</b>" in result


@pytest.mark.asyncio
@patch("bot.services.asyncio.to_thread", new_callable=AsyncMock)
async def test_search_symbols_returns_quotes(mock_to_thread):
    mock_to_thread.return_value = [
        {"symbol": "AAPL", "shortname": "Apple Inc.", "exchDisp": "NASDAQ", "typeDisp": "Equity"},
    ]

    results = await main.search_symbols("Apple")
    assert results[0]["symbol"] == "AAPL"
    mock_to_thread.assert_awaited_once()

    # Second call within TTL should hit the cache, not call yfinance again.
    await main.search_symbols("Apple")
    mock_to_thread.assert_awaited_once()


@pytest.mark.asyncio
@patch("bot.services.asyncio.to_thread", new_callable=AsyncMock)
async def test_search_symbols_handles_failure(mock_to_thread):
    mock_to_thread.side_effect = Exception("Yahoo unavailable")

    results = await main.search_symbols("Apple")
    assert results == []


@pytest.mark.asyncio
@patch("bot.services._fetch_yfinance_info")
async def test_yfinance_timeout(mock_fetch):
    config.PROVIDER_TIMEOUT = 0.05
    config.INITIAL_BACKOFF = 0.001

    def slow_call(*args, **kwargs):
        time.sleep(0.1)
        return {"regularMarketPrice": 100}

    mock_fetch.side_effect = slow_call

    result = await main.get_quote_formatted("AAPL")
    assert "Sorry, I encountered an error fetching data for <b>AAPL</b>" in result


@pytest.mark.asyncio
@patch("bot.services._fetch_yfinance_info")
async def test_transient_failure_retry(mock_fetch):
    config.INITIAL_BACKOFF = 0.001
    mock_fetch.side_effect = [
        Exception("Transient timeout"),
        {"regularMarketPrice": 150.5, "shortName": "Apple Inc."},
    ]

    result = await main.get_quote_formatted("AAPL")
    assert "<b>Price:</b> $150.50" in result
    assert mock_fetch.call_count == 2
