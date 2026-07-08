from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Chat, Message, Update, User
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from bot import config
from bot.commands.crypto import crypto
from bot.utils import USER_COOLDOWNS


@pytest.fixture(autouse=True)
def reset_states():
    config.ALLOWED_CHAT_IDS.clear()
    USER_COOLDOWNS.clear()


@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.first_name = "TestUser"
    update.effective_user.id = 11111
    update.message = AsyncMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.effective_message = AsyncMock(spec=Message)
    update.effective_message.chat_id = 12345
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
@patch("bot.commands.crypto.get_quote_formatted", new_callable=AsyncMock)
async def test_crypto_command_with_args_no_usd(mock_get_quote, mock_update, mock_context):
    mock_context.args = ["BTC"]
    mock_get_quote.return_value = "The current price of BTC/USD is $50000.0"

    await crypto(mock_update, mock_context)

    mock_get_quote.assert_called_once_with("BTC-USD", display_symbol="BTC/USD", is_crypto=True)
    assert mock_update.message.reply_text.call_count == 1
    mock_update.message.reply_text.assert_any_call("The current price of BTC/USD is $50000.0", parse_mode="HTML")


@pytest.mark.asyncio
async def test_crypto_command_without_args(mock_update, mock_context):
    mock_context.args = []

    await crypto(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    assert "Please provide a crypto symbol" in mock_update.message.reply_text.call_args[0][0]
    assert mock_update.message.reply_text.call_args[1]["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_crypto_command_invalid_args(mock_update, mock_context):
    mock_context.args = ["BTC_invalid$"]

    await crypto(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    assert "Invalid crypto symbol format" in mock_update.message.reply_text.call_args[0][0]
    assert mock_update.message.reply_text.call_args[1]["parse_mode"] == "HTML"
