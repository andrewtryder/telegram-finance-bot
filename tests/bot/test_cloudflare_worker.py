"""Unit tests for the Python Cloudflare Worker (storage and webhook)."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from cloudflare.storage import D1Storage
from cloudflare.webhook import (
    compact_number,
    format_number,
    format_price,
    handle_request,
    market_symbol,
    same_secret,
    validate_webhook_config,
)


class MockRequest:
    def __init__(self, method="POST", url="https://example.com/webhook", headers=None, body=None):
        self.method = method
        self.url = url
        self.headers = headers or {}
        self.body = body or ""

    async def text(self):
        return self.body


@pytest.mark.asyncio
async def test_d1_storage_watchlist():
    db = MagicMock()
    stmt = MagicMock()
    db.prepare.return_value.bind.return_value = stmt
    stmt.all = AsyncMock(return_value={"results": [{"symbol": "AAPL"}, {"symbol": "MSFT"}]})

    storage = D1Storage(db)
    symbols = await storage.watchlist(123)
    assert symbols == ["AAPL", "MSFT"]

    # Test add watchlist success
    stmt_add = MagicMock()
    stmt_add.run = AsyncMock(return_value={"meta": {"changes": 1}})
    db.prepare.return_value.bind.return_value = stmt_add
    ok, msg = await storage.add_watchlist(123, "GOOG")
    assert ok is True
    assert "Added GOOG" in msg

    # Test add watchlist duplicate / full
    stmt_add.run = AsyncMock(return_value={"meta": {"changes": 0}})
    stmt_add.first = AsyncMock(return_value={"symbol": "GOOG"})
    ok, msg = await storage.add_watchlist(123, "GOOG")
    assert ok is False
    assert "already on your watchlist" in msg

    # Test remove watchlist
    stmt_del = MagicMock()
    stmt_del.run = AsyncMock(return_value={"meta": {"changes": 1}})
    db.prepare.return_value.bind.return_value = stmt_del
    ok, msg = await storage.remove_watchlist(123, "GOOG")
    assert ok is True
    assert "Removed GOOG" in msg


@pytest.mark.asyncio
async def test_d1_storage_alerts():
    db = MagicMock()
    storage = D1Storage(db)

    # Test add alert
    stmt_add = MagicMock()
    stmt_add.first = AsyncMock(return_value={"id": 42})
    db.prepare.return_value.bind.return_value = stmt_add
    ok, msg = await storage.add_alert(100, 200, "AAPL", "above", 200.0)
    assert ok is True
    assert "Alert #42" in msg

    # Test remove alert
    stmt_rm = MagicMock()
    stmt_rm.run = AsyncMock(return_value={"meta": {"changes": 1}})
    db.prepare.return_value.bind.return_value = stmt_rm
    ok, msg = await storage.remove_alert(100, 42)
    assert ok is True
    assert "Removed alert #42" in msg


def test_market_symbol_and_formatting():
    assert market_symbol("aapl") == "AAPL"
    assert market_symbol("btc", crypto=True) == "BTC-USD"
    assert market_symbol("btc", infer_crypto=True) == "BTC-USD"
    assert market_symbol("invalid$symbol") is None

    assert format_number(1234.567) == "1,234.57"
    assert format_price(1234.5, "USD") == "$1,234.50"
    assert compact_number(1_500_000_000) == "1.50B"
    assert compact_number(2_000_000) == "2.00M"


def test_secret_validation():
    assert same_secret("my-secret", "my-secret") is True
    assert same_secret("my-secret", "wrong-secret") is False


def test_validate_webhook_config():
    valid_env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123:token",
        "TELEGRAM_WEBHOOK_SECRET": "secret123",
        "WATCHLIST_ENABLED": "false",
        "ALERTS_ENABLED": "false",
        "STORAGE_BACKEND": "none",
    }
    validate_webhook_config(valid_env)

    invalid_mode = {**valid_env, "BOT_MODE": "polling"}
    with pytest.raises(ValueError, match="BOT_MODE"):
        validate_webhook_config(invalid_mode)

    invalid_features = {**valid_env, "WATCHLIST_ENABLED": "true", "STORAGE_BACKEND": "none"}
    with pytest.raises(ValueError, match="require persistent storage"):
        validate_webhook_config(invalid_features)

    sqlite_backend = {**valid_env, "STORAGE_BACKEND": "sqlite"}
    with pytest.raises(ValueError, match="only supports none or d1"):
        validate_webhook_config(sqlite_backend)

    d1_without_db = {**valid_env, "STORAGE_BACKEND": "d1"}
    with pytest.raises(ValueError, match="requires a DB binding"):
        validate_webhook_config(d1_without_db)


@pytest.mark.asyncio
async def test_handle_request_health_and_secret():
    env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123:token",
        "TELEGRAM_WEBHOOK_SECRET": "test_secret",
        "STORAGE_BACKEND": "none",
    }
    # Health check GET
    health_req = MockRequest(method="GET", url="https://example.com/health")
    res = await handle_request(health_req, env)
    assert res.status == 200

    # 404 for unknown path
    unknown_req = MockRequest(method="GET", url="https://example.com/unknown")
    res = await handle_request(unknown_req, env)
    assert res.status == 404

    # 403 on missing secret
    webhook_req = MockRequest(method="POST", url="https://example.com/webhook", body=json.dumps({"update_id": 1}))
    res = await handle_request(webhook_req, env)
    assert res.status == 403

    # 400 on bad JSON body
    bad_req = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test_secret"},
        body="invalid json",
    )
    res = await handle_request(bad_req, env)
    assert res.status == 400


@pytest.mark.asyncio
async def test_handle_request_allowed_chat_ids(monkeypatch):
    env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123:token",
        "TELEGRAM_WEBHOOK_SECRET": "test_secret",
        "STORAGE_BACKEND": "none",
        "ALLOWED_CHAT_IDS": "999",
    }
    send_mock = AsyncMock()
    monkeypatch.setattr("cloudflare.webhook.telegram", send_mock)

    req = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test_secret"},
        body=json.dumps(
            {
                "update_id": 1,
                "message": {"text": "/stock AAPL", "chat": {"id": 123}, "from": {"id": 456}},
            }
        ),
    )
    res = await handle_request(req, env)
    assert res.status == 200
    send_mock.assert_awaited_once()
    assert "Access denied" in send_mock.await_args[0][2]["text"]


@pytest.mark.asyncio
async def test_handle_request_duplicate_update_stateless(monkeypatch):
    from cloudflare import webhook

    webhook.recent_updates.clear()
    env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123:token",
        "TELEGRAM_WEBHOOK_SECRET": "test_secret",
        "STORAGE_BACKEND": "none",
    }
    send_mock = AsyncMock()
    monkeypatch.setattr("cloudflare.webhook.telegram", send_mock)

    req1 = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test_secret"},
        body=json.dumps(
            {
                "update_id": 1001,
                "message": {"text": "/help", "chat": {"id": 123}, "from": {"id": 456}},
            }
        ),
    )
    res1 = await handle_request(req1, env)
    assert res1.status == 200
    send_mock.assert_awaited_once()

    # Second request with same update_id
    req2 = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test_secret"},
        body=json.dumps(
            {
                "update_id": 1001,
                "message": {"text": "/help", "chat": {"id": 123}, "from": {"id": 456}},
            }
        ),
    )
    res2 = await handle_request(req2, env)
    assert res2.status == 200
    data = json.loads(res2.body)
    assert data.get("duplicate") is True
    # send_mock was not called a second time
    assert send_mock.await_count == 1


@pytest.mark.asyncio
async def test_handle_request_edited_message(monkeypatch):
    env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123:token",
        "TELEGRAM_WEBHOOK_SECRET": "test_secret",
        "STORAGE_BACKEND": "none",
    }
    send_mock = AsyncMock()
    monkeypatch.setattr("cloudflare.webhook.telegram", send_mock)

    req = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test_secret"},
        body=json.dumps(
            {
                "update_id": 2001,
                "edited_message": {"text": "/help", "chat": {"id": 123}, "from": {"id": 456}},
            }
        ),
    )
    res = await handle_request(req, env)
    assert res.status == 200
    send_mock.assert_awaited_once()
    assert "Financial Market Bot" in send_mock.await_args[0][2]["text"]


@pytest.mark.asyncio
async def test_handle_request_bot_mentions(monkeypatch):
    env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123:token",
        "TELEGRAM_WEBHOOK_SECRET": "test_secret",
        "STORAGE_BACKEND": "none",
    }

    async def mock_tg(env, method, body=None):
        if method == "getMe":
            return {"username": "MyFinanceBot"}
        return {}

    monkeypatch.setattr("cloudflare.webhook.telegram", mock_tg)

    # Addressed to another bot -> ignored silently
    req_other = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test_secret"},
        body=json.dumps(
            {
                "update_id": 3001,
                "message": {"text": "/stock@OtherBot AAPL", "chat": {"id": 123}, "from": {"id": 456}},
            }
        ),
    )
    res_other = await handle_request(req_other, env)
    assert res_other.status == 200

    # Addressed to our bot -> handled
    send_mock = AsyncMock()

    async def mock_tg_handled(env, method, body=None):
        if method == "getMe":
            return {"username": "MyFinanceBot"}
        return await send_mock(env, method, body)

    monkeypatch.setattr("cloudflare.webhook.telegram", mock_tg_handled)
    req_mine = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test_secret"},
        body=json.dumps(
            {
                "update_id": 3002,
                "message": {"text": "/help@MyFinanceBot", "chat": {"id": 123}, "from": {"id": 456}},
            }
        ),
    )
    res_mine = await handle_request(req_mine, env)
    assert res_mine.status == 200
    send_mock.assert_awaited_once()


def test_d1_schema_sqlite_execution():
    import sqlite3
    from pathlib import Path

    migration_file = Path(__file__).parents[2] / "cloudflare" / "migrations" / "0001_storage.sql"
    sql = migration_file.read_text(encoding="utf-8")

    conn = sqlite3.connect(":memory:")
    conn.executescript(sql)

    # Verify tables
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert {"watchlist", "alerts", "processed_updates"}.issubset(tables)

    # Test processed_updates constraint
    conn.execute("INSERT INTO processed_updates (update_id) VALUES (42)")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO processed_updates (update_id) VALUES (42)")


@pytest.mark.asyncio
async def test_command_parity_executions(monkeypatch):
    from cloudflare.webhook import reply_for

    env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123:token",
        "TELEGRAM_WEBHOOK_SECRET": "test_secret",
        "STORAGE_BACKEND": "none",
        "WATCHLIST_ENABLED": "false",
        "ALERTS_ENABLED": "false",
    }
    dummy_msg = {"chat": {"id": 123}, "from": {"id": 456, "first_name": "Alice"}}

    # Mock data_request for stock and crypto
    async def mock_data_req(path, params):
        if "chart/" in path:
            sym = path.split("chart/")[-1]
            price = 50000.0 if "BTC" in sym else 150.0
            prev = 48000.0 if "BTC" in sym else 145.0
            return {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "currency": "USD",
                                "regularMarketPrice": price,
                                "previousClose": prev,
                                "shortName": "Test Asset",
                                "regularMarketDayLow": price * 0.95,
                                "regularMarketDayHigh": price * 1.05,
                                "fiftyTwoWeekLow": price * 0.7,
                                "fiftyTwoWeekHigh": price * 1.2,
                                "regularMarketVolume": 1000000,
                            },
                            "indicators": {"quote": [{"close": [prev, price]}]},
                            "timestamp": [1700000000, 1700086400],
                        }
                    ]
                }
            }
        return {}

    monkeypatch.setattr("cloudflare.webhook.data_request", mock_data_req)
    monkeypatch.setattr("cloudflare.webhook.company_summary", AsyncMock(return_value={}))

    # 1. /stock AAPL
    stock_reply = await reply_for("stock", ["AAPL"], dummy_msg, env)
    assert "AAPL" in stock_reply
    assert "$150.00" in stock_reply

    # 2. /crypto BTC
    crypto_reply = await reply_for("crypto", ["BTC"], dummy_msg, env)
    assert "BTC/USD" in crypto_reply
    assert "$50,000.00" in crypto_reply

    # 3. /indices
    indices_reply = await reply_for("indices", [], dummy_msg, env)
    assert "Major Market Indices" in indices_reply
    assert "S&amp;P 500" in indices_reply

    # 4. /compare AAPL MSFT
    compare_reply = await reply_for("compare", ["AAPL", "MSFT"], dummy_msg, env)
    assert "Compare" in compare_reply
    assert "AAPL" in compare_reply
    assert "MSFT" in compare_reply

    # 5. /chart AAPL
    chart_reply = await reply_for("chart", ["AAPL"], dummy_msg, env)
    assert isinstance(chart_reply, dict)
    assert "image" in chart_reply
    assert chart_reply["image"].startswith(b"\x89PNG")
    assert "AAPL" in chart_reply["caption"]
