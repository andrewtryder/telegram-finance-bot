import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update, User, Message, Chat, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ChatAction
from telegram.ext import ContextTypes
import main

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
    assert 'reply_markup' in kwargs
    assert isinstance(kwargs['reply_markup'], ReplyKeyboardMarkup)

@patch('main.TWELVEDATA_API_KEY', 'fake_key')
@patch('main.requests.get')
def test_get_quote_formatted_success(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"close": "150.50", "name": "Apple Inc.", "change": "1.50", "percent_change": "1.0", "datetime": "2023-10-10"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = main.get_quote_formatted("AAPL")
    assert "Apple Inc. (AAPL)" in result
    assert "$150.50" in result

@patch('main.TWELVEDATA_API_KEY', 'fake_key')
@patch('main.requests.get')
def test_get_quote_formatted_error_status(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "error", "message": "Invalid ticker"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = main.get_quote_formatted("INVALID")
    assert "Error from TwelveData: Invalid ticker" in result

@patch('main.TWELVEDATA_API_KEY', 'fake_key')
@patch('main.requests.get')
def test_get_quote_formatted_exception(mock_get):
    mock_get.side_effect = Exception("Network error")

    result = main.get_quote_formatted("AAPL")
    assert "Sorry, I couldn't fetch the data right now" in result

@patch('main.TWELVEDATA_API_KEY', None)
def test_get_quote_formatted_no_api_key():
    result = main.get_quote_formatted("AAPL")
    assert "Error: Twelve Data API Key is not configured." in result



@pytest.mark.asyncio
@patch('main.get_quote_formatted')
async def test_stock_command_with_args(mock_get_quote, mock_update, mock_context):
    mock_context.args = ['AAPL']
    mock_get_quote.return_value = "The current price of AAPL is $150.5"

    await main.stock(mock_update, mock_context)

    mock_context.bot.send_chat_action.assert_called_once_with(chat_id=12345, action=ChatAction.TYPING)
    mock_update.message.reply_text.assert_called_once_with("The current price of AAPL is $150.5", parse_mode='Markdown')

@pytest.mark.asyncio
async def test_stock_command_without_args(mock_update, mock_context):
    mock_context.args = []

    await main.stock(mock_update, mock_context)

    mock_context.bot.send_chat_action.assert_called_once_with(chat_id=12345, action=ChatAction.TYPING)
    mock_update.message.reply_text.assert_called_once_with("Please provide a stock ticker. Example: `/stock AAPL`", parse_mode='Markdown')

@pytest.mark.asyncio
@patch('main.get_quote_formatted')
async def test_crypto_command_with_args_no_usd(mock_get_quote, mock_update, mock_context):
    mock_context.args = ['BTC']
    mock_get_quote.return_value = "The current price of BTC/USD is $50000.0"

    await main.crypto(mock_update, mock_context)

    mock_context.bot.send_chat_action.assert_called_once_with(chat_id=12345, action=ChatAction.TYPING)
    mock_update.message.reply_text.assert_called_once_with("The current price of BTC/USD is $50000.0", parse_mode='Markdown')

@pytest.mark.asyncio
async def test_crypto_command_without_args(mock_update, mock_context):
    mock_context.args = []

    await main.crypto(mock_update, mock_context)

    mock_context.bot.send_chat_action.assert_called_once_with(chat_id=12345, action=ChatAction.TYPING)
    mock_update.message.reply_text.assert_called_once_with("Please provide a crypto symbol. Example: `/crypto BTC`", parse_mode='Markdown')
