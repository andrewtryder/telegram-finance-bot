import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update, User, Message, Chat, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
import main

@pytest.fixture(autouse=True)
def clear_cache():
    if hasattr(main, 'API_CACHE'):
        main.API_CACHE.clear()

@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.first_name = "TestUser"
    update.message = AsyncMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.id = 12345
    return update

@pytest.fixture
def mock_context():
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    context.bot = MagicMock()
    context.bot.send_chat_action = AsyncMock()
    return context

@pytest.mark.asyncio
async def test_start_command(mock_update, mock_context):
    await main.start(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args
    assert "Hi TestUser!" in args[0]
    assert "/stock" in args[0]

@pytest.mark.asyncio
@patch('main.yf.Ticker')
async def test_get_quote_formatted_success(mock_ticker):
    mock_instance = MagicMock()
    mock_instance.info = {
        "regularMarketPrice": 150.50,
        "shortName": "Apple Inc.",
        "regularMarketChange": 1.50,
        "regularMarketChangePercent": 1.00,
        "currency": "USD"
    }
    mock_ticker.return_value = mock_instance

    result = await main.get_quote_formatted("AAPL")
    assert "Price: 150.50 USD" in result
    assert "Apple Inc. (AAPL)" in result

@pytest.mark.asyncio
@patch('main.yf.Ticker')
async def test_get_quote_formatted_not_found(mock_ticker):
    mock_instance = MagicMock()
    mock_instance.info = {}
    mock_ticker.return_value = mock_instance

    result = await main.get_quote_formatted("INVALID")
    assert "Could not find quote data for INVALID" in result

@pytest.mark.asyncio
@patch('main.yf.Ticker')
async def test_get_quote_formatted_exception(mock_ticker):
    mock_ticker.side_effect = Exception("YF error")

    result = await main.get_quote_formatted("AAPL")
    assert "Sorry, I couldn't fetch the data right now" in result

@pytest.mark.asyncio
@patch('main.get_quote_formatted', new_callable=AsyncMock)
async def test_stock_command_with_args(mock_get_quote, mock_update, mock_context):
    mock_context.args = ['AAPL']
    mock_get_quote.return_value = "The current price of AAPL is 150.50 USD"

    await main.stock(mock_update, mock_context)

    assert mock_update.message.reply_text.call_count == 1
    mock_update.message.reply_text.assert_any_call("The current price of AAPL is 150.50 USD", parse_mode='Markdown')

@pytest.mark.asyncio
@patch('main.get_quote_formatted', new_callable=AsyncMock)
async def test_crypto_command_conversion(mock_get_quote, mock_update, mock_context):
    mock_context.args = ['BTC/USD']
    mock_get_quote.return_value = "Price of BTC-USD"

    await main.crypto(mock_update, mock_context)

    mock_get_quote.assert_called_with("BTC-USD")
    mock_update.message.reply_text.assert_called_with("Price of BTC-USD", parse_mode='Markdown')

    mock_context.args = ['ETH']
    await main.crypto(mock_update, mock_context)
    mock_get_quote.assert_called_with("ETH-USD")

@pytest.mark.asyncio
@patch('main.TWELVEDATA_API_KEY', 'fake_key')
@patch('main.httpx.AsyncClient.get', new_callable=AsyncMock)
async def test_search_command_success(mock_get, mock_update, mock_context):
    mock_context.args = ['Apple']
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"symbol": "AAPL", "instrument_name": "Apple Inc.", "exchange": "NASDAQ", "instrument_type": "Common Stock"}
        ]
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    await main.search(mock_update, mock_context)

    mock_update.message.reply_text.assert_called()
    args, kwargs = mock_update.message.reply_text.call_args
    assert "AAPL" in args[0]
    assert "Apple Inc." in args[0]

@pytest.mark.asyncio
@patch('main.yf.Ticker')
async def test_indices_command(mock_ticker, mock_update, mock_context):
    mock_instance = MagicMock()
    mock_instance.info = {
        "regularMarketPrice": 4500.0,
        "regularMarketChangePercent": 0.5
    }
    mock_ticker.return_value = mock_instance

    await main.indices(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args
    assert "S&P 500" in args[0]
    assert "4,500.00" in args[0]
