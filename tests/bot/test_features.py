import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot import storage
from bot.metrics import record_command, record_error, reset, snapshot


@pytest.fixture(autouse=True)
def _reset_metrics():
    reset()
    yield
    reset()


@pytest.fixture
def tmp_storage(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr("bot.config.DATA_DIR", tmp)
        storage._db_path = None
        storage.init_storage()
        yield tmp
        storage._db_path = None


def test_metrics_snapshot():
    record_command("stock")
    record_command("stock")
    record_error()
    snap = snapshot()
    assert snap["commands_total"]["stock"] == 2
    assert snap["errors_total"] == 1


def test_watchlist_add_list_remove(tmp_storage):
    ok, msg = storage.watchlist_add(1, "AAPL")
    assert ok
    assert storage.watchlist_list(1) == ["AAPL"]
    ok, msg = storage.watchlist_add(1, "AAPL")
    assert not ok
    ok, msg = storage.watchlist_remove(1, "AAPL")
    assert ok
    assert storage.watchlist_list(1) == []


def test_watchlist_max(tmp_storage):
    for i in range(storage.MAX_WATCHLIST):
        ok, _ = storage.watchlist_add(42, f"T{i}")
        assert ok
    ok, msg = storage.watchlist_add(42, "EXTRA")
    assert not ok
    assert "full" in msg.lower()


def test_alert_crud(tmp_storage):
    ok, msg, alert_id = storage.alert_add(1, 9, "MSFT", "above", 400.0)
    assert ok and alert_id
    rows = storage.alert_list(1)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "MSFT"
    ok, msg = storage.alert_remove(1, alert_id)
    assert ok
    assert storage.alert_list(1) == []


@pytest.mark.asyncio
async def test_compare_command():
    from bot.commands.compare import compare
    from bot.utils import USER_COOLDOWNS

    update = MagicMock()
    update.effective_chat.id = 1
    update.effective_user.id = 2
    update.effective_user.first_name = "Test"
    update.message.text = "/compare AAPL MSFT"
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["AAPL", "MSFT"]
    context.bot.send_chat_action = AsyncMock()

    with patch("bot.commands.compare._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.side_effect = [
            {"regularMarketPrice": 100, "previousClose": 90, "shortName": "A"},
            {"regularMarketPrice": 200, "previousClose": 210, "shortName": "M"},
        ]
        USER_COOLDOWNS.clear()
        await compare(update, context)

    args, kwargs = update.message.reply_text.call_args
    assert "Compare" in args[0]
    assert "AAPL" in args[0]
    assert "MSFT" in args[0]
    assert kwargs.get("parse_mode") == "HTML"


@pytest.mark.asyncio
@patch("bot.services.asyncio.to_thread", new_callable=AsyncMock)
async def test_premarket_line_in_quote(mock_to_thread):
    from bot import services as main

    main.QUOTE_CACHE.clear()
    mock_to_thread.return_value = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 150.50,
        "previousClose": 149.0,
        "marketState": "PRE",
        "preMarketPrice": 151.0,
        "preMarketChange": 0.5,
        "preMarketChangePercent": 0.33,
        "regularMarketTime": 1672531200,
    }
    result = await main.get_quote_formatted("AAPL")
    assert "Pre:" in result
    assert "$151.00" in result
