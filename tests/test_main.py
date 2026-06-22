import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes
import main

@pytest.fixture(autouse=True)
def clear_cache():
    main.API_CACHE.clear()



@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.first_name = "TestUser"
    update.message = AsyncMock(spec=Message)
    update.message.reply_text = AsyncMock()
    return update

@pytest.fixture
def mock_context():
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    return context

@pytest.mark.asyncio
async def test_start_command(mock_update, mock_context):
    await main.start(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args
    assert "Hi TestUser!" in args[0]
    assert "/stock" in args[0]

@pytest.mark.asyncio
@patch('main.TWELVEDATA_API_KEY', 'fake_key')
@patch('main.httpx.AsyncClient.get', new_callable=AsyncMock)
async def test_get_quote_formatted_success(mock_get):
    mock_response = MagicMock()
    mock_response.json = MagicMock()
    mock_response.json.return_value = {"close": "150.50", "name": "Apple Inc.", "change": "1.50", "percent_change": "1.00", "datetime": "2023-01-01"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = await main.get_quote_formatted("AAPL")
    assert "Price: $150.50" in result

@pytest.mark.asyncio
@patch('main.TWELVEDATA_API_KEY', 'fake_key')
@patch('main.httpx.AsyncClient.get', new_callable=AsyncMock)
async def test_get_quote_formatted_error_status(mock_get):
    mock_response = MagicMock()
    mock_response.json = MagicMock()
    mock_response.json.return_value = {"status": "error", "message": "Invalid ticker"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = await main.get_quote_formatted("INVALID")
    assert "Error from TwelveData: Invalid ticker" in result

@pytest.mark.asyncio
@patch('main.TWELVEDATA_API_KEY', 'fake_key')
@patch('main.httpx.AsyncClient.get', new_callable=AsyncMock)
async def test_get_quote_formatted_exception(mock_get):
    mock_get.side_effect = Exception("Network error")

    result = await main.get_quote_formatted("AAPL")
    assert "Sorry, I couldn't fetch the data right now" in result

@pytest.mark.asyncio
@patch('main.TWELVEDATA_API_KEY', None)
async def test_get_quote_formatted_no_api_key():
    result = await main.get_quote_formatted("AAPL")
    assert "Error: Twelve Data API Key is not configured." in result

@pytest.mark.asyncio
@patch('main.get_quote_formatted', new_callable=AsyncMock)
async def test_stock_command_with_args(mock_get_price, mock_update, mock_context):
    mock_context.args = ['AAPL']
    mock_get_price.return_value = "The current price of AAPL is $150.5"

    await main.stock(mock_update, mock_context)

    assert mock_update.message.reply_text.call_count == 1
    mock_update.message.reply_text.assert_any_call("The current price of AAPL is $150.5", parse_mode='Markdown')

@pytest.mark.asyncio
async def test_stock_command_without_args(mock_update, mock_context):
    mock_context.args = []

    await main.stock(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once_with("Please provide a stock ticker. Example: `/stock AAPL`", parse_mode='Markdown')

@pytest.mark.asyncio
@patch('main.get_quote_formatted', new_callable=AsyncMock)
async def test_crypto_command_with_args_no_usd(mock_get_price, mock_update, mock_context):
    mock_context.args = ['BTC']
    mock_get_price.return_value = "The current price of BTC/USD is $50000.0"

    await main.crypto(mock_update, mock_context)

    assert mock_update.message.reply_text.call_count == 1
    mock_update.message.reply_text.assert_any_call("The current price of BTC/USD is $50000.0", parse_mode='Markdown')

@pytest.mark.asyncio
async def test_crypto_command_without_args(mock_update, mock_context):
    mock_context.args = []

    await main.crypto(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once_with("Please provide a crypto symbol. Example: `/crypto BTC`", parse_mode='Markdown')
