import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot import config
from bot import services as main


@pytest.fixture(autouse=True)
def clear_cache_and_reset():
    main.API_CACHE.clear()
    main.QUOTE_CACHE.clear()
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
@patch("bot.services.HTTP_CLIENT")
async def test_fetch_with_cache_redacts_secrets(mock_http_client, caplog):
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": []}
    mock_http_client.get = AsyncMock(return_value=mock_response)

    with caplog.at_level(logging.INFO):
        await main.fetch_with_cache(
            "https://api.twelvedata.com/symbol_search",
            {"symbol": "Apple", "apikey": "secret_key_123"},
        )
        for record in caplog.records:
            assert "secret_key_123" not in record.message
            assert "apikey=" not in record.message

    cache_keys = list(main.API_CACHE.keys())
    assert len(cache_keys) == 1
    safe_key = cache_keys[0]
    assert safe_key[0] == "https://api.twelvedata.com/symbol_search"
    assert dict(safe_key[1])["apikey"] == "[REDACTED]"


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
