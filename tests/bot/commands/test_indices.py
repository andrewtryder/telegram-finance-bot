from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Chat, Message, Update, User
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from bot import config
from bot.commands.indices import indices
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
@patch("bot.commands.indices._get_yfinance_info", new_callable=AsyncMock)
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
    assert "S&amp;P 500" in args[0]
    assert "5,432.10" in args[0]
    assert "+0.45%" in args[0]
    assert "Dow Jones" in args[0]
    assert "Nasdaq" in args[0]
    assert kwargs["parse_mode"] == "HTML"
