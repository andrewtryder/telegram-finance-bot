import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update, User, Message, Chat, ReplyKeyboardMarkup
from telegram import BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
from telegram.constants import ChatType
from telegram.ext import ContextTypes, Application
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
    assert "reply_markup" in kwargs

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
    assert isinstance(private_call.kwargs["scope"], BotCommandScopeAllPrivateChats)
    assert isinstance(group_call.kwargs["scope"], BotCommandScopeAllGroupChats)

@pytest.mark.asyncio
async def test_ignore_non_command_group_messages(mock_update, mock_context):
    mock_update.effective_chat.id = 999
    await main._ignore_non_command_group_messages(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()
