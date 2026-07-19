"""Command-level tests for watchlist, chart, alert, and compare."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Chat, Message, Update, User
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from bot import config, storage
from bot.utils import USER_COOLDOWNS


@pytest.fixture(autouse=True)
def reset_states(tmp_path, monkeypatch):
    config.ALLOWED_CHAT_IDS.clear()
    USER_COOLDOWNS.clear()
    monkeypatch.setattr("bot.config.DATA_DIR", str(tmp_path))
    storage._db_path = None
    storage.init_storage()
    yield
    storage._db_path = None


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
    context.bot.send_message = AsyncMock()
    return context


# --- watchlist ---


@pytest.mark.asyncio
async def test_watchlist_empty(mock_update, mock_context):
    from bot.commands.watchlist import watchlist

    mock_context.args = []
    await watchlist(mock_update, mock_context)
    text = mock_update.message.reply_text.call_args[0][0]
    assert "empty" in text.lower()


@pytest.mark.asyncio
async def test_watchlist_add_and_show(mock_update, mock_context):
    from bot.commands.watchlist import watchlist

    mock_context.args = ["add", "AAPL"]
    await watchlist(mock_update, mock_context)
    assert "Added AAPL" in mock_update.message.reply_text.call_args[0][0]

    USER_COOLDOWNS.clear()
    mock_update.message.reply_text.reset_mock()
    mock_context.args = []
    with patch("bot.commands.watchlist._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = {"regularMarketPrice": 100, "previousClose": 90}
        await watchlist(mock_update, mock_context)

    text = mock_update.message.reply_text.call_args[0][0]
    assert "Watchlist" in text
    assert "AAPL" in text


@pytest.mark.asyncio
async def test_watchlist_remove(mock_update, mock_context):
    from bot.commands.watchlist import watchlist

    storage.watchlist_add(11111, "MSFT")
    mock_context.args = ["remove", "MSFT"]
    await watchlist(mock_update, mock_context)
    assert "Removed MSFT" in mock_update.message.reply_text.call_args[0][0]
    assert storage.watchlist_list(11111) == []


@pytest.mark.asyncio
async def test_watchlist_anonymous_user(mock_update, mock_context):
    from bot.commands.watchlist import watchlist

    mock_update.effective_user = None
    mock_context.args = []
    await watchlist(mock_update, mock_context)
    text = mock_update.message.reply_text.call_args[0][0]
    assert "identity" in text.lower() or "anonymous" in text.lower()


@pytest.mark.asyncio
async def test_watchlist_persists_for_same_user_different_chat(mock_update, mock_context):
    from bot.commands.watchlist import watchlist

    mock_context.args = ["add", "NVDA"]
    await watchlist(mock_update, mock_context)

    USER_COOLDOWNS.clear()
    # Same user, different chat (e.g. channel)
    mock_update.effective_chat.id = -100999
    mock_context.args = []
    with patch("bot.commands.watchlist._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = {"regularMarketPrice": 500, "previousClose": 490}
        await watchlist(mock_update, mock_context)

    assert "NVDA" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_watchlist_add_crypto_shorthand(mock_update, mock_context):
    from bot.commands.watchlist import watchlist

    mock_context.args = ["add", "BTC"]
    await watchlist(mock_update, mock_context)
    assert "Added BTC-USD" in mock_update.message.reply_text.call_args[0][0]
    assert storage.watchlist_list(11111) == ["BTC-USD"]

    USER_COOLDOWNS.clear()
    mock_update.message.reply_text.reset_mock()
    mock_context.args = []
    with patch("bot.commands.watchlist._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = {"regularMarketPrice": 0.42, "previousClose": 0.40}
        await watchlist(mock_update, mock_context)

    text = mock_update.message.reply_text.call_args[0][0]
    assert "BTC/USD" in text
    assert "$0.4200" in text
    mock_info.assert_awaited_once_with("BTC-USD")


# --- chart ---


@pytest.mark.asyncio
async def test_chart_without_args(mock_update, mock_context):
    from bot.commands.chart import chart

    await chart(mock_update, mock_context)
    assert "Usage" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_chart_invalid_period(mock_update, mock_context):
    from bot.commands.chart import chart

    mock_context.args = ["AAPL", "2w"]
    await chart(mock_update, mock_context)
    assert "Period must be" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
@patch("bot.commands.chart.get_history_chart_png", new_callable=AsyncMock)
async def test_chart_success(mock_png, mock_update, mock_context):
    from bot.commands.chart import chart

    mock_png.return_value = b"\x89PNG\r\n\x1a\nfake"
    mock_context.args = ["AAPL", "3mo"]
    await chart(mock_update, mock_context)
    mock_png.assert_awaited_once_with("AAPL", period="3mo")
    mock_update.message.reply_photo.assert_awaited_once()
    assert "AAPL" in mock_update.message.reply_photo.call_args.kwargs["caption"]


@pytest.mark.asyncio
@patch("bot.commands.chart.get_history_chart_png", new_callable=AsyncMock)
async def test_chart_crypto_shorthand(mock_png, mock_update, mock_context):
    from bot.commands.chart import chart

    mock_png.return_value = b"\x89PNG\r\n\x1a\nfake"
    mock_context.args = ["BTC", "1mo"]
    await chart(mock_update, mock_context)
    mock_png.assert_awaited_once_with("BTC-USD", period="1mo")
    assert "BTC/USD" in mock_update.message.reply_photo.call_args.kwargs["caption"]


@pytest.mark.asyncio
@patch("bot.commands.chart.get_history_chart_png", new_callable=AsyncMock)
async def test_chart_no_data(mock_png, mock_update, mock_context):
    from bot.commands.chart import chart

    mock_png.return_value = None
    mock_context.args = ["ZZZZ"]
    await chart(mock_update, mock_context)
    assert "Could not build a chart" in mock_update.message.reply_text.call_args[0][0]


# --- alert ---


@pytest.mark.asyncio
async def test_alert_list_empty(mock_update, mock_context):
    from bot.commands.alerts import alert

    mock_context.args = ["list"]
    await alert(mock_update, mock_context)
    assert "No alerts" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_alert_add_list_remove(mock_update, mock_context):
    from bot.commands.alerts import alert

    mock_context.args = ["add", "AAPL", "above", "200"]
    await alert(mock_update, mock_context)
    assert "Alert #" in mock_update.message.reply_text.call_args[0][0]

    USER_COOLDOWNS.clear()
    mock_update.message.reply_text.reset_mock()
    mock_context.args = ["list"]
    await alert(mock_update, mock_context)
    text = mock_update.message.reply_text.call_args[0][0]
    assert "AAPL" in text
    assert "above" in text

    rows = storage.alert_list(12345)
    alert_id = rows[0]["id"]
    USER_COOLDOWNS.clear()
    mock_update.message.reply_text.reset_mock()
    mock_context.args = ["remove", str(alert_id)]
    await alert(mock_update, mock_context)
    assert "Removed" in mock_update.message.reply_text.call_args[0][0]
    assert storage.alert_list(12345) == []


@pytest.mark.asyncio
async def test_alert_add_crypto_shorthand(mock_update, mock_context):
    from bot.commands.alerts import alert

    mock_context.args = ["add", "BTC", "above", "100000"]
    await alert(mock_update, mock_context)
    assert "BTC-USD" in mock_update.message.reply_text.call_args[0][0]
    rows = storage.alert_list(12345)
    assert rows[0]["symbol"] == "BTC-USD"


@pytest.mark.asyncio
async def test_alert_add_bad_direction(mock_update, mock_context):
    from bot.commands.alerts import alert

    mock_context.args = ["add", "AAPL", "around", "200"]
    await alert(mock_update, mock_context)
    assert "above" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_alert_add_bad_price(mock_update, mock_context):
    from bot.commands.alerts import alert

    mock_context.args = ["add", "AAPL", "above", "nope"]
    await alert(mock_update, mock_context)
    assert "number" in mock_update.message.reply_text.call_args[0][0].lower()


# --- compare ---


@pytest.mark.asyncio
async def test_compare_too_few_args(mock_update, mock_context):
    from bot.commands.compare import compare

    mock_context.args = ["AAPL"]
    await compare(mock_update, mock_context)
    text = mock_update.message.reply_text.call_args[0][0]
    assert "2–4" in text or "2-4" in text


@pytest.mark.asyncio
async def test_compare_invalid_ticker(mock_update, mock_context):
    from bot.commands.compare import compare

    mock_context.args = ["AAPL", "BAD$"]
    await compare(mock_update, mock_context)
    assert "Invalid ticker" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_compare_crypto_shorthand(mock_update, mock_context):
    from bot.commands.compare import compare

    mock_context.args = ["BTC", "ETH"]
    with patch("bot.commands.compare._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.side_effect = [
            {"regularMarketPrice": 100000, "previousClose": 99000},
            {"regularMarketPrice": 3500, "previousClose": 3400},
        ]
        await compare(mock_update, mock_context)

    assert mock_info.await_args_list[0].args[0] == "BTC-USD"
    assert mock_info.await_args_list[1].args[0] == "ETH-USD"
    text = mock_update.message.reply_text.call_args[0][0]
    assert "BTC/USD" in text
    assert "ETH/USD" in text
