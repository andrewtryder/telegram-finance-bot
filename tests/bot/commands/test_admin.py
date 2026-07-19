"""Tests for /admin stats command."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Chat, Message, Update, User
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from bot import config
from bot.metrics import format_stats_html, record_command, record_error, record_provider_error, reset
from bot.utils import USER_COOLDOWNS


@pytest.fixture(autouse=True)
def reset_states():
    config.ALLOWED_CHAT_IDS.clear()
    config.ADMIN_USER_IDS.clear()
    USER_COOLDOWNS.clear()
    reset()
    yield
    config.ADMIN_USER_IDS.clear()
    reset()


@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.first_name = "Owner"
    update.effective_user.id = 999001
    update.message = AsyncMock(spec=Message)
    update.message.text = "/admin"
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


def test_format_stats_html():
    record_command("stock")
    record_command("stock")
    record_command("crypto")
    record_error()
    record_provider_error("yfinance")
    text = format_stats_html()
    assert "Admin stats" in text
    assert "stock: 2" in text
    assert "crypto: 1" in text
    assert "Errors:</b> 1" in text
    assert "yfinance: 1" in text


@pytest.mark.asyncio
async def test_admin_denied_when_not_configured(mock_update, mock_context):
    from bot.commands.admin import admin

    await admin(mock_update, mock_context)
    assert "Access denied" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_admin_denied_for_non_admin(mock_update, mock_context):
    from bot.commands.admin import admin

    config.ADMIN_USER_IDS.add(111)
    mock_update.effective_user.id = 222
    await admin(mock_update, mock_context)
    assert "Access denied" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_admin_stats_for_admin(mock_update, mock_context):
    from bot.commands.admin import admin

    config.ADMIN_USER_IDS.add(999001)
    record_command("watchlist")
    mock_context.args = ["stats"]
    await admin(mock_update, mock_context)
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Admin stats" in text
    assert "watchlist" in text


@pytest.mark.asyncio
async def test_admin_default_action_is_stats(mock_update, mock_context):
    from bot.commands.admin import admin

    config.ADMIN_USER_IDS.add(999001)
    mock_context.args = []
    await admin(mock_update, mock_context)
    assert "Admin stats" in mock_update.message.reply_text.call_args[0][0]
