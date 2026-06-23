import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes
from telegram.constants import ChatType
from bot.commands.indices import indices

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
@patch('bot.commands.indices._get_yfinance_info', new_callable=AsyncMock)
async def test_indices_command(mock_get_info, mock_update, mock_context):
    mock_get_info.side_effect = [
        {"regularMarketPrice": 5432.10, "regularMarketChangePercent": 0.45},
        {"regularMarketPrice": 42100.50, "regularMarketChangePercent": -0.12},
        {"regularMarketPrice": 17800.25, "regularMarketChangePercent": 0.88},
    ]

    await indices(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args
    assert "Major Market Indices" in args[0]
    assert "S&P 500" in args[0]
    assert "5,432.10" in args[0]
    assert "+0.45%" in args[0]
    assert "Dow Jones" in args[0]
    assert "Nasdaq" in args[0]
