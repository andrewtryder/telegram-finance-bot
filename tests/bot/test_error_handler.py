from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Message, Update
from telegram.error import Conflict
from telegram.ext import ContextTypes

from bot.main import error_handler


@pytest.fixture
def mock_context():
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.error = None
    return context


@pytest.mark.asyncio
async def test_error_handler_skips_honeybadger_for_conflict(mock_context):
    mock_context.error = Conflict("terminated by other getUpdates request")

    with (
        patch("bot.main.notify_honeybadger") as notify,
        patch("bot.main.record_error") as record,
        patch("bot.main.logger") as logger,
    ):
        await error_handler(None, mock_context)

    notify.assert_not_called()
    record.assert_not_called()
    logger.warning.assert_called_once()
    assert "getUpdates" in logger.warning.call_args.args[0]


@pytest.mark.asyncio
async def test_error_handler_notifies_honeybadger_for_other_errors(mock_context):
    err = RuntimeError("boom")
    mock_context.error = err

    update = MagicMock(spec=Update)
    update.effective_chat = MagicMock()
    update.effective_chat.id = 99
    update.effective_chat.type = "private"
    update.effective_user = MagicMock()
    update.effective_user.id = 42
    update.effective_message = MagicMock()
    update.effective_message.text = "/stock AAPL"
    update.message = AsyncMock(spec=Message)
    update.message.reply_text = AsyncMock()

    with (
        patch("bot.main.notify_honeybadger") as notify,
        patch("bot.main.record_error") as record,
        patch("bot.main.logger"),
    ):
        await error_handler(update, mock_context)

    record.assert_called_once()
    notify.assert_called_once_with(
        err,
        chat_id=99,
        chat_type="private",
        user_id=42,
        message_text="/stock AAPL",
    )
    update.message.reply_text.assert_awaited_once()
