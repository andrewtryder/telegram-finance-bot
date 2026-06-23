import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes
from telegram.constants import ChatType, ParseMode
from bot.commands.search import search

@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.first_name = "TestUser"
    update.message = AsyncMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.effective_message = AsyncMock(spec=Message)
    update.effective_message.chat_id = 12345
    return update

@pytest.fixture
def mock_context():
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    context.bot = MagicMock()
    context.bot.send_chat_action = AsyncMock()
    return context

@pytest.mark.asyncio
@patch('bot.commands.search.TWELVEDATA_API_KEY', None)
async def test_search_no_api_key(mock_update, mock_context):
    mock_context.args = ['Apple']

    await search(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once_with("Error: Twelve Data API Key is not configured.")

@pytest.mark.asyncio
@patch('bot.commands.search.TWELVEDATA_API_KEY', 'fake_key')
@patch('bot.commands.search.fetch_with_cache', new_callable=AsyncMock)
async def test_search_markdown_injection(mock_fetch, mock_update, mock_context):
    mock_context.args = ['*malicious_query*']
    mock_fetch.return_value = {
        "data": [
            {
                "symbol": "TEST*",
                "instrument_name": "Test Co.",
                "exchange": "NYSE",
                "instrument_type": "Common Stock"
            }
        ]
    }

    await search(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args

    assert kwargs.get('parse_mode') == ParseMode.MARKDOWN_V2

    # Check that the malicious query and returned symbol are escaped
    assert "\\*malicious\\_query\\*" in args[0]
    assert "TEST\\*" in args[0]

@pytest.mark.asyncio
@patch('bot.commands.search.TWELVEDATA_API_KEY', 'fake_key')
@patch('bot.commands.search.fetch_with_cache', new_callable=AsyncMock)
async def test_search_markdown_injection_no_results(mock_fetch, mock_update, mock_context):
    mock_context.args = ['*malicious_query*']
    mock_fetch.return_value = {"data": []}

    await search(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args

    assert kwargs.get('parse_mode') == ParseMode.MARKDOWN_V2
    assert "\\*malicious\\_query\\*" in args[0]
