"""Tests for jobs, compact quotes, extended hours, and alert limits."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot import storage
from bot.metrics import record_command, reset, snapshot
from bot.services import _format_price, format_compact_quote


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.config.DATA_DIR", str(tmp_path))
    storage._db_path = None
    storage.init_storage()
    yield
    storage._db_path = None


@pytest.fixture(autouse=True)
def _reset_metrics():
    reset()
    yield
    reset()


def test_format_price_crypto_sub_dollar():
    assert _format_price(0.1234, True) == "$0.1234"
    assert _format_price(1.5, True) == "$1.50"
    assert _format_price(0.1234, False) == "$0.12"


def test_format_compact_quote_up():
    line = format_compact_quote(
        {"regularMarketPrice": 110, "previousClose": 100},
        "AAPL",
    )
    assert "AAPL" in line
    assert "$110.00" in line
    assert "+" in line


def test_format_compact_quote_crypto_sub_dollar():
    line = format_compact_quote(
        {"regularMarketPrice": 0.0842, "previousClose": 0.0800},
        "DOGE/USD",
        is_crypto=True,
    )
    assert "$0.0842" in line
    assert "DOGE/USD" in line


def test_format_compact_quote_unavailable():
    assert "unavailable" in format_compact_quote({}, "XYZ").lower()
    assert "unavailable" in format_compact_quote({"shortName": "X"}, "XYZ").lower()


@pytest.mark.asyncio
@patch("bot.services.asyncio.to_thread", new_callable=AsyncMock)
async def test_postmarket_line_in_quote(mock_to_thread):
    from bot import services as main

    main.QUOTE_CACHE.clear()
    mock_to_thread.return_value = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 150.50,
        "previousClose": 149.0,
        "marketState": "POST",
        "postMarketPrice": 149.25,
        "postMarketChange": -1.25,
        "postMarketChangePercent": -0.83,
        "regularMarketTime": 1672531200,
    }
    result = await main.get_quote_formatted("AAPL")
    assert "Post:" in result
    assert "$149.25" in result


@pytest.mark.asyncio
@patch("bot.services.asyncio.to_thread", new_callable=AsyncMock)
async def test_get_history_chart_png_empty(mock_to_thread):
    from bot import services as main

    mock_to_thread.return_value = None
    assert await main.get_history_chart_png("AAPL") is None


def test_alert_max(tmp_storage):
    for i in range(storage.MAX_ALERTS):
        ok, _, _ = storage.alert_add(1, 9, f"T{i}", "above", float(i))
        assert ok
    ok, msg, alert_id = storage.alert_add(1, 9, "EXTRA", "above", 1.0)
    assert not ok
    assert alert_id is None
    assert "limit" in msg.lower()


def test_alert_invalid_direction(tmp_storage):
    ok, msg, alert_id = storage.alert_add(1, 9, "AAPL", "sideways", 100.0)
    assert not ok
    assert alert_id is None


@pytest.mark.asyncio
async def test_log_metrics_job(caplog):
    from bot.jobs import log_metrics_job

    record_command("stock")
    with caplog.at_level(logging.INFO):
        await log_metrics_job(MagicMock())
    assert any("metrics_snapshot" in r.message for r in caplog.records)
    assert '"stock": 1' in caplog.text or '"stock":1' in caplog.text.replace(" ", "")


@pytest.mark.asyncio
async def test_check_price_alerts_job_fires_and_deletes(tmp_storage):
    from bot.jobs import check_price_alerts_job

    ok, _, alert_id = storage.alert_add(42, 7, "AAPL", "above", 100.0)
    assert ok

    context = MagicMock()
    context.bot.send_message = AsyncMock()

    with patch("bot.jobs._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = {"regularMarketPrice": 150.0}
        await check_price_alerts_job(context)

    context.bot.send_message.assert_awaited_once()
    kwargs = context.bot.send_message.call_args.kwargs
    assert kwargs["chat_id"] == 42
    assert "AAPL" in kwargs["text"]
    assert storage.alert_list(42) == []


@pytest.mark.asyncio
async def test_check_price_alerts_job_below_not_fired(tmp_storage):
    from bot.jobs import check_price_alerts_job

    storage.alert_add(42, 7, "AAPL", "below", 50.0)
    context = MagicMock()
    context.bot.send_message = AsyncMock()

    with patch("bot.jobs._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = {"regularMarketPrice": 150.0}
        await check_price_alerts_job(context)

    context.bot.send_message.assert_not_called()
    assert len(storage.alert_list(42)) == 1


@pytest.mark.asyncio
async def test_check_price_alerts_job_noop_when_empty(tmp_storage):
    from bot.jobs import check_price_alerts_job

    context = MagicMock()
    context.bot.send_message = AsyncMock()
    await check_price_alerts_job(context)
    context.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_check_price_alerts_job_fetches_symbols_in_parallel(tmp_storage):
    from bot.jobs import check_price_alerts_job

    storage.alert_add(1, 7, "AAPL", "above", 100.0)
    storage.alert_add(1, 7, "MSFT", "above", 200.0)
    context = MagicMock()
    context.bot.send_message = AsyncMock()

    with patch("bot.jobs._get_yfinance_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = {"regularMarketPrice": 50.0}
        await check_price_alerts_job(context)

    assert mock_info.await_count == 2
    called = {c.args[0] for c in mock_info.await_args_list}
    assert called == {"AAPL", "MSFT"}


def test_metrics_provider_error():
    from bot.metrics import record_provider_error

    record_provider_error("yfinance")
    assert snapshot()["provider_errors"]["yfinance"] == 1
