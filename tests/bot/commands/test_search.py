from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Chat, Message, Update, User
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from bot import config
from bot.commands.search import search
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
@patch("bot.commands.search.search_symbols", new_callable=AsyncMock)
async def test_search_html_escaping(mock_search, mock_update, mock_context):
    mock_context.args = ["<malicious_query>"]
    mock_search.return_value = [
        {
            "symbol": "TEST<",
            "shortname": "Test Co.",
            "exchDisp": "NYSE",
            "typeDisp": "Equity",
            "quoteType": "EQUITY",
        }
    ]

    await search(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args

    assert kwargs.get("parse_mode") == "HTML"
    assert "&lt;malicious_query&gt;" in args[0]
    assert "TEST&lt;" in args[0]


@pytest.mark.asyncio
@patch("bot.commands.search.search_symbols", new_callable=AsyncMock)
async def test_search_no_results(mock_search, mock_update, mock_context):
    mock_context.args = ["<malicious_query>"]
    mock_search.return_value = []

    await search(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args

    assert kwargs.get("parse_mode") == "HTML"
    assert "&lt;malicious_query&gt;" in args[0]


@pytest.mark.asyncio
@patch("bot.commands.search.search_symbols", new_callable=AsyncMock)
async def test_search_filters_irrelevant_types(mock_search, mock_update, mock_context):
    mock_context.args = ["Apple"]
    mock_search.return_value = [
        {
            "symbol": "AAPL",
            "shortname": "Apple Inc.",
            "exchDisp": "NASDAQ",
            "typeDisp": "Equity",
            "quoteType": "EQUITY",
        },
        {"symbol": "AAPL-NEWS", "shortname": "Some article", "quoteType": "FUTURE"},
    ]

    await search(mock_update, mock_context)

    args, kwargs = mock_update.message.reply_text.call_args
    assert "AAPL" in args[0]
    assert "AAPL-NEWS" not in args[0]


@pytest.mark.asyncio
async def test_search_overlong_query(mock_update, mock_context):
    mock_context.args = ["A" * 65]

    await search(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args
    assert "Search query is too long" in args[0]
