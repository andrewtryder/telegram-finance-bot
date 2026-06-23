import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update, User, Message, Chat, ReplyKeyboardMarkup
from telegram import BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
from telegram.constants import ChatType
from telegram.ext import ContextTypes, Application
import main

@pytest.fixture(autouse=True)
def clear_cache():
    if hasattr(main, 'API_CACHE'):
        main.API_CACHE.clear()
    if hasattr(main, 'QUOTE_CACHE'):
        main.QUOTE_CACHE.clear()

@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.first_name = "TestUser"
    update.message = AsyncMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.id = 12345
    update.effective_chat.type = ChatType.PRIVATE
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
    assert "reply_markup" not in kwargs


@pytest.mark.asyncio
async def test_start_command_group_no_keyboard(mock_update, mock_context):
    mock_update.effective_chat.type = ChatType.GROUP

    await main.start(mock_update, mock_context)

    _, kwargs = mock_update.message.reply_text.call_args
    assert "reply_markup" not in kwargs


@pytest.mark.asyncio
async def test_help_or_start_command_group_no_keyboard(mock_update, mock_context):
    mock_update.effective_chat.type = ChatType.SUPERGROUP

    await main.start(mock_update, mock_context)

    _, kwargs = mock_update.message.reply_text.call_args
    assert "reply_markup" not in kwargs


@pytest.mark.asyncio
async def test_setup_commands():
    application = MagicMock(spec=Application)
    application.bot = MagicMock()
    application.bot.set_my_commands = AsyncMock()

    await main.setup_commands(application)

    assert application.bot.set_my_commands.call_count == 2
    private_call, group_call = application.bot.set_my_commands.call_args_list
    assert private_call.args[0] == main.BOT_COMMANDS
    assert isinstance(private_call.kwargs["scope"], BotCommandScopeAllPrivateChats)
    assert group_call.args[0] == main.GROUP_COMMANDS
    assert isinstance(group_call.kwargs["scope"], BotCommandScopeAllGroupChats)


@pytest.mark.asyncio
async def test_ignore_non_command_group_messages(mock_update, mock_context):
    mock_update.effective_chat.id = 999

    await main._ignore_non_command_group_messages(mock_update, mock_context)

    mock_update.message.reply_text.assert_not_called()



@pytest.mark.asyncio
@patch('main.asyncio.to_thread', new_callable=AsyncMock)
async def test_get_quote_formatted_success(mock_to_thread):
    mock_to_thread.return_value = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 150.50,
        "regularMarketChange": 1.50,
        "regularMarketChangePercent": 1.00,
        "regularMarketTime": 1672531200,
    }

    result = await main.get_quote_formatted("AAPL")
    assert "Price: $150.50" in result
    assert "Apple Inc." in result

@pytest.mark.asyncio
@patch('main.asyncio.to_thread', new_callable=AsyncMock)
async def test_get_quote_formatted_missing_price(mock_to_thread):
    mock_to_thread.return_value = {"shortName": "Invalid"}

    result = await main.get_quote_formatted("INVALID")
    assert "Could not find quote data for INVALID" in result

@pytest.mark.asyncio
@patch('main.asyncio.to_thread', new_callable=AsyncMock)
async def test_get_quote_formatted_exception(mock_to_thread):
    mock_to_thread.side_effect = Exception("Network error")

    result = await main.get_quote_formatted("AAPL")
    assert "Sorry, I couldn't fetch the data right now" in result

@pytest.mark.asyncio
@patch('main.get_quote_formatted', new_callable=AsyncMock)
async def test_stock_command_with_args(mock_get_quote, mock_update, mock_context):
    mock_context.args = ['AAPL']
    mock_get_quote.return_value = "The current price of AAPL is $150.5"

    await main.stock(mock_update, mock_context)

    mock_get_quote.assert_called_once_with("AAPL", "AAPL")
    assert mock_update.message.reply_text.call_count == 1
    mock_update.message.reply_text.assert_any_call("The current price of AAPL is $150.5", parse_mode='Markdown')

@pytest.mark.asyncio
async def test_stock_command_without_args(mock_update, mock_context):
    mock_context.args = []

    await main.stock(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once_with("Please provide a stock ticker. Example: `/stock AAPL`", parse_mode='Markdown')

@pytest.mark.asyncio
@patch('main.get_quote_formatted', new_callable=AsyncMock)
async def test_crypto_command_with_args_no_usd(mock_get_quote, mock_update, mock_context):
    mock_context.args = ['BTC']
    mock_get_quote.return_value = "The current price of BTC/USD is $50000.0"

    await main.crypto(mock_update, mock_context)

    mock_get_quote.assert_called_once_with("BTC-USD", "BTC/USD")
    assert mock_update.message.reply_text.call_count == 1
    mock_update.message.reply_text.assert_any_call("The current price of BTC/USD is $50000.0", parse_mode='Markdown')

@pytest.mark.asyncio
async def test_crypto_command_without_args(mock_update, mock_context):
    mock_context.args = []

    await main.crypto(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once_with("Please provide a crypto symbol. Example: `/crypto BTC`", parse_mode='Markdown')

@pytest.mark.asyncio
@patch('main._get_yfinance_info', new_callable=AsyncMock)
async def test_indices_command(mock_get_info, mock_update, mock_context):
    mock_get_info.side_effect = [
        {"regularMarketPrice": 5432.10, "regularMarketChangePercent": 0.45},
        {"regularMarketPrice": 42100.50, "regularMarketChangePercent": -0.12},
        {"regularMarketPrice": 17800.25, "regularMarketChangePercent": 0.88},
    ]

    await main.indices(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args
    assert "Major Market Indices" in args[0]
    assert "S&P 500" in args[0]
    assert "5,432.10" in args[0]
    assert "+0.45%" in args[0]
    assert "Dow Jones" in args[0]
    assert "Nasdaq Composite" in args[0]

@pytest.mark.asyncio
@patch('main.TWELVEDATA_API_KEY', None)
async def test_search_no_api_key(mock_update, mock_context):
    mock_context.args = ['Apple']

    await main.search(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once_with("Error: Twelve Data API Key is not configured.")
