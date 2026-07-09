from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import (
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    Chat,
    Message,
    ReplyKeyboardRemove,
    Update,
    User,
)
from telegram.constants import ChatType
from telegram.ext import Application, ContextTypes

from bot.commands import basics as main


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
    assert "Hello TestUser!" in args[0]
    assert "/stock" in args[0]
    assert isinstance(kwargs.get("reply_markup"), ReplyKeyboardRemove)
    assert kwargs.get("parse_mode") == "HTML"


@pytest.mark.asyncio
async def test_start_command_group_no_keyboard(mock_update, mock_context):
    mock_update.effective_chat.type = ChatType.GROUP
    await main.start(mock_update, mock_context)
    _, kwargs = mock_update.message.reply_text.call_args
    assert "reply_markup" not in kwargs
    assert kwargs.get("parse_mode") == "HTML"


@pytest.mark.asyncio
async def test_help_or_start_command_group_no_keyboard(mock_update, mock_context):
    mock_update.effective_chat.type = ChatType.SUPERGROUP
    await main.start(mock_update, mock_context)
    _, kwargs = mock_update.message.reply_text.call_args
    assert "reply_markup" not in kwargs
    assert kwargs.get("parse_mode") == "HTML"


@pytest.mark.asyncio
async def test_setup_commands():
    application = MagicMock(spec=Application)
    application.bot = MagicMock()
    application.bot.delete_my_commands = AsyncMock()
    await main.setup_commands(application)
    assert application.bot.delete_my_commands.call_count == 3
    private_call, group_call, default_call = application.bot.delete_my_commands.call_args_list
    assert isinstance(private_call.kwargs["scope"], BotCommandScopeAllPrivateChats)
    assert isinstance(group_call.kwargs["scope"], BotCommandScopeAllGroupChats)


@pytest.mark.asyncio
async def test_ignore_non_command_group_messages(mock_update, mock_context):
    mock_update.effective_chat.id = 999
    await main._ignore_non_command_group_messages(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_start_command_with_specific_help(mock_update, mock_context):
    mock_context.args = ["stock"]
    await main.start(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args
    assert "Shows a quote snapshot" in args[0]
