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
    with pytest.raises(ValueError, match="require a database"):
        validate_webhook_config(invalid_features)


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
