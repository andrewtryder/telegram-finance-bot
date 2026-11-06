"""Command-level tests for chart, compare, and retired commands (watchlist & alert)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Chat, Message, Update, User
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from bot import config
from bot.commands.basics import retired_command
from bot.commands.chart import chart
from bot.commands.compare import compare
from bot.utils import USER_COOLDOWNS


@pytest.fixture(autouse=True)
def reset_states():
    config.ALLOWED_CHAT_IDS.clear()
    USER_COOLDOWNS.clear()
    yield


@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.first_name = "TestUser"
    update.effective_user.id = 11111
    update.message = AsyncMock(spec=Message)
    update.message.text = "/cmd"
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()
    update.effective_message = update.message
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
    context.bot.send_message = AsyncMock()
    return context


# --- retired commands ---


@pytest.mark.asyncio
async def test_retired_command_reply(mock_update, mock_context):
    await retired_command(mock_update, mock_context)
    mock_update.message.reply_text.assert_awaited_once()
    reply = mock_update.message.reply_text.await_args[0][0]
    assert "retired" in reply.lower()
    assert "stateless" in reply.lower()


# --- chart ---


@pytest.mark.asyncio
async def test_chart_no_args(mock_update, mock_context):
    mock_context.args = []
    await chart(mock_update, mock_context)
    mock_update.message.reply_text.assert_awaited_once()
    assert "Usage: <code>/chart" in mock_update.message.reply_text.await_args[0][0]


@pytest.mark.asyncio
async def test_chart_bad_period(mock_update, mock_context):
    mock_context.args = ["AAPL", "5y"]
    await chart(mock_update, mock_context)
    assert "Period must be one of" in mock_update.message.reply_text.await_args[0][0]


@pytest.mark.asyncio
async def test_chart_success(mock_update, mock_context):
    mock_context.args = ["AAPL"]
    with patch("bot.commands.chart.get_history_chart_png", new_callable=AsyncMock) as mock_get_chart:
        mock_get_chart.return_value = b"\x89PNGfake"
        await chart(mock_update, mock_context)

    mock_update.message.reply_photo.assert_awaited_once()
    assert mock_update.message.reply_photo.await_args.kwargs["caption"] == "📈 AAPL · 1mo"


@pytest.mark.asyncio
async def test_chart_render_failure(mock_update, mock_context):
    mock_context.args = ["AAPL"]
    with patch("bot.commands.chart.get_history_chart_png", new_callable=AsyncMock) as mock_get_chart:
        mock_get_chart.return_value = None
        await chart(mock_update, mock_context)

    mock_update.message.reply_text.assert_awaited_once()
    assert "Could not build a chart" in mock_update.message.reply_text.await_args[0][0]


# --- compare ---


@pytest.mark.asyncio
async def test_compare_too_few_args(mock_update, mock_context):
    mock_context.args = ["AAPL"]
    await compare(mock_update, mock_context)
    assert "Provide 2–4 tickers" in mock_update.message.reply_text.await_args[0][0]


@pytest.mark.asyncio
async def test_compare_too_many_args(mock_update, mock_context):
    mock_context.args = ["A", "B", "C", "D", "E"]
    await compare(mock_update, mock_context)
    assert "Provide 2–4 tickers" in mock_update.message.reply_text.await_args[0][0]


@pytest.mark.asyncio
async def test_compare_success(mock_update, mock_context):
    mock_context.args = ["AAPL", "MSFT"]
    sample = {"regularMarketPrice": 150.0, "previousClose": 140.0}
    with patch("bot.commands.compare._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = sample
        await compare(mock_update, mock_context)

    mock_update.message.reply_text.assert_awaited_once()
    text = mock_update.message.reply_text.await_args[0][0]
    assert "AAPL" in text
    assert "MSFT" in text
    assert "$150.00" in text
