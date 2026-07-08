from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Chat, Message, Update, User
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from bot import config
from bot.commands import stocks as main
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
@patch("bot.commands.stocks.get_quote_formatted", new_callable=AsyncMock)
async def test_stock_command_with_args(mock_get_quote, mock_update, mock_context):
    mock_context.args = ["AAPL"]
    mock_get_quote.return_value = "The current price of AAPL is $150.5"

    await main.stock(mock_update, mock_context)

    mock_get_quote.assert_called_once_with("AAPL", display_symbol="AAPL", is_crypto=False)
    assert mock_update.message.reply_text.call_count == 1
    mock_update.message.reply_text.assert_any_call("The current price of AAPL is $150.5", parse_mode="HTML")


@pytest.mark.asyncio
async def test_stock_command_without_args(mock_update, mock_context):
    mock_context.args = []

    await main.stock(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    assert "Please provide a stock ticker" in mock_update.message.reply_text.call_args[0][0]
    assert mock_update.message.reply_text.call_args[1]["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_stock_command_invalid_ticker(mock_update, mock_context):
    mock_context.args = ["AAPL_invalid$"]

    await main.stock(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    assert "Invalid stock ticker format" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
@patch("bot.commands.stocks._get_yfinance_info", new_callable=AsyncMock)
async def test_stockinfo_command(mock_get_info, mock_update, mock_context):
    mock_context.args = ["AAPL"]
    mock_get_info.return_value = {
        "shortName": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "marketCap": 3200000000000,
        "website": "https://www.apple.com",
        "longBusinessSummary": "Designs electronics.",
    }

    await main.stockinfo(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args
    assert "Apple Inc. (AAPL)" in args[0]
    assert "<b>Sector:</b> Technology" in args[0]
    assert '<b>Website:</b> <a href="https://www.apple.com">https://www.apple.com</a>' in args[0]
    assert kwargs["parse_mode"] == "HTML"


@pytest.mark.asyncio
@patch("bot.commands.stocks._get_yfinance_news", new_callable=AsyncMock)
async def test_stocknews_command(mock_get_news, mock_update, mock_context):
    mock_context.args = ["AAPL"]
    mock_get_news.return_value = [
        {"title": "News 1", "link": "https://news1.com"},
        {"title": "News 2", "link": "not_valid"},
    ]

    await main.stocknews(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args
    assert "Recent news for AAPL" in args[0]
    assert '<a href="https://news1.com">News 1</a>' in args[0]
    assert "News 2" in args[0]
    assert "not_valid" not in args[0]


@pytest.mark.asyncio
@patch("bot.commands.stocks._get_yfinance_info", new_callable=AsyncMock)
async def test_marketcap_command(mock_get_info, mock_update, mock_context):
    mock_context.args = ["AAPL"]
    mock_get_info.return_value = {"shortName": "Apple Inc.", "marketCap": 3200000000000}

    await main.marketcap(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args
    assert "Apple Inc. (AAPL)" in args[0]
    assert "Market Cap: <b>$3.20T</b>" in args[0]
    assert kwargs["parse_mode"] == "HTML"
