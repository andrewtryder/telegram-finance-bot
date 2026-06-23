import pytest
from unittest.mock import AsyncMock, patch
from bot import services as main

@pytest.fixture(autouse=True)
def clear_cache():
    if hasattr(main, 'API_CACHE'):
        main.API_CACHE.clear()
    if hasattr(main, 'QUOTE_CACHE'):
        main.QUOTE_CACHE.clear()

@pytest.mark.asyncio
@patch('bot.services.asyncio.to_thread', new_callable=AsyncMock)
async def test_get_quote_formatted_success(mock_to_thread):
    mock_to_thread.return_value = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 150.50,
        "regularMarketChange": 1.50,
        "regularMarketChangePercent": 1.00,
        "regularMarketTime": 1672531200,
    }

    result = await main.get_quote_formatted("AAPL")
    assert "Price:** $150.50" in result

@pytest.mark.asyncio
@patch('bot.services.asyncio.to_thread', new_callable=AsyncMock)
async def test_get_quote_formatted_missing_price(mock_to_thread):
    mock_to_thread.return_value = {"shortName": "Invalid"}

    result = await main.get_quote_formatted("INVALID")
    assert "Could not fetch current price for **INVALID**" in result

@pytest.mark.asyncio
@patch('bot.services.asyncio.to_thread', new_callable=AsyncMock)
async def test_get_quote_formatted_exception(mock_to_thread):
    mock_to_thread.side_effect = Exception("Network error")

    result = await main.get_quote_formatted("AAPL")
    assert "Sorry, I encountered an error fetching data for **AAPL**" in result
