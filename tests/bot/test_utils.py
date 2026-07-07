from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Chat, Message, Update, User
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from bot import config
from bot.utils import USER_COOLDOWNS, command_guard


@pytest.fixture(autouse=True)
def reset_states():
    config.ALLOWED_CHAT_IDS.clear()
    USER_COOLDOWNS.clear()


@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 11111
    update.message = AsyncMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.id = 12345
    update.effective_chat.type = ChatType.PRIVATE
    return update


@pytest.fixture
def mock_context():
    return MagicMock(spec=ContextTypes.DEFAULT_TYPE)


@pytest.mark.asyncio
async def test_command_guard_no_allowlist(mock_update, mock_context):
    called = False

    @command_guard
    async def sample_handler(update, context):
        nonlocal called
        called = True

    await sample_handler(mock_update, mock_context)
    assert called is True
    mock_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_command_guard_authorized_chat(mock_update, mock_context):
    config.ALLOWED_CHAT_IDS.add(12345)
    called = False

    @command_guard
    async def sample_handler(update, context):
        nonlocal called
        called = True

    await sample_handler(mock_update, mock_context)
    assert called is True
    mock_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_command_guard_unauthorized_chat(mock_update, mock_context):
    config.ALLOWED_CHAT_IDS.add(99999)  # different chat ID
    called = False

    @command_guard
    async def sample_handler(update, context):
        nonlocal called
        called = True

    await sample_handler(mock_update, mock_context)
    assert called is False
    mock_update.message.reply_text.assert_called_once_with("Access denied. This bot is private.")


@pytest.mark.asyncio
async def test_command_guard_allow_all_with_zero(mock_update, mock_context):
    config.ALLOWED_CHAT_IDS.add(0)  # 0 enables public mode / allow anyone
    called = False

    @command_guard
    async def sample_handler(update, context):
        nonlocal called
        called = True

    await sample_handler(mock_update, mock_context)
    assert called is True
    mock_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_command_guard_rate_limiting_active(mock_update, mock_context):
    # Standard rate limiting should trigger if no allowlist is active (or if it is bypassed by 0)
    called_count = 0

    @command_guard
    async def sample_handler(update, context):
        nonlocal called_count
        called_count += 1

    # First call: OK
    await sample_handler(mock_update, mock_context)
    assert called_count == 1

    # Second call (immediate): throttled
    await sample_handler(mock_update, mock_context)
    assert called_count == 1
    mock_update.message.reply_text.assert_called_once_with("Too many requests. Please wait a moment.")
