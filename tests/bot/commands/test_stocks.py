import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes
from telegram.constants import ChatType
from bot.commands import stocks as main

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
@patch('bot.commands.stocks.get_quote_formatted', new_callable=AsyncMock)
async def test_stock_command_with_args(mock_get_quote, mock_update, mock_context):
    mock_context.args = ['AAPL']
    mock_get_quote.return_value = "The current price of AAPL is $150.5"

    await main.stock(mock_update, mock_context)

    mock_get_quote.assert_called_once_with("AAPL", display_symbol="AAPL")
    assert mock_update.message.reply_text.call_count == 1
    mock_update.message.reply_text.assert_any_call("The current price of AAPL is $150.5", parse_mode='Markdown')

@pytest.mark.asyncio
async def test_stock_command_without_args(mock_update, mock_context):
    mock_context.args = []

    await main.stock(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once_with("Please provide a stock ticker. Example: `/stock AAPL`", parse_mode='Markdown')
