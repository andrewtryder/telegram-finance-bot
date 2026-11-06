"""Unit tests for the stateless Python Cloudflare Worker."""

import datetime
import json
import zoneinfo
from unittest.mock import AsyncMock

import pytest

from cloudflare.webhook import (
    _cache_get,
    _cache_set,
    compact_number,
    format_number,
    format_price,
    format_quote,
    handle_request,
    market_symbol,
    quote,
    recent_updates,
    reply_for,
    same_secret,
    timed_fetch,
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


@pytest.fixture(autouse=True)
def clean_recent_updates():
    recent_updates.clear()
    yield
    recent_updates.clear()


def test_market_symbol():
    assert market_symbol("aapl") == "AAPL"
    assert market_symbol("btc", infer_crypto=True) == "BTC-USD"
    assert market_symbol("eth", crypto=True) == "ETH-USD"
    assert market_symbol("BTC/USD") == "BTC-USD"
    assert market_symbol("invalid$$$") is None


def test_format_number():
    assert format_number(123.456) == "123.46"
    assert format_number(0.123456, crypto=True) == "0.1235"
    assert format_number(10.5, crypto=True) == "10.50"


def test_format_price():
    assert format_price(150.25, "USD") == "$150.25"
    assert format_price(0.005, "USD", crypto=True) == "$0.0050"
    assert format_price(100.0, "EUR") == "EUR 100.00"
    assert format_price(None, "USD") is None


def test_compact_number():
    assert compact_number(1500000000000) == "1.50T"
    assert compact_number(2500000000) == "2.50B"
    assert compact_number(3500000) == "3.50M"
    assert compact_number(4500) == "4.50K"
    assert compact_number(42) == "42.00"
    assert compact_number(None) is None


def test_same_secret():
    assert same_secret("correct_secret", "correct_secret") is True
    assert same_secret("wrong_secret", "correct_secret") is False


def test_validate_webhook_config():
    valid_env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "TELEGRAM_WEBHOOK_SECRET": "my_super_secret_token_123",
    }
    validate_webhook_config(valid_env)

    # Invalid BOT_MODE
    with pytest.raises(ValueError, match="BOT_MODE must be webhook"):
        validate_webhook_config({**valid_env, "BOT_MODE": "polling"})

    # Missing token
    with pytest.raises(ValueError, match="Telegram token and valid webhook secret are required"):
        validate_webhook_config({**valid_env, "TELEGRAM_BOT_TOKEN": ""})

    # Invalid secret
    with pytest.raises(ValueError, match="Telegram token and valid webhook secret are required"):
        validate_webhook_config({**valid_env, "TELEGRAM_WEBHOOK_SECRET": "invalid secret with spaces!"})


def test_format_quote_pre_market():
    tz = zoneinfo.ZoneInfo("America/New_York")
    ref_now = datetime.datetime(2026, 11, 10, 8, 30, tzinfo=tz)
    pre_time = int(datetime.datetime(2026, 11, 10, 8, 15, tzinfo=tz).timestamp())
    reg_time = int(datetime.datetime(2026, 11, 9, 16, 0, tzinfo=tz).timestamp())
    q = {
        "symbol": "AAPL",
        "price": 250.0,
        "previous": 248.5,
        "open": 249.0,
        "meta": {
            "currency": "USD",
            "shortName": "Apple Inc.",
            "marketState": "PRE",
            "preMarketPrice": 252.15,
            "preMarketChange": 3.65,
            "preMarketChangePercent": 1.47,
            "regularMarketTime": reg_time,
            "preMarketTime": pre_time,
        },
    }
    text = format_quote(q, crypto=False, now_dt=ref_now)
    assert "Apple Inc. (AAPL)" in text
    assert "Regular Price:</b> $250.00" in text
    assert "Previous Close:</b> $248.50" in text
    assert "🌅 <b>Pre-Market:</b> $252.15" in text
    assert "+$3.65" in text
    assert "(+1.47%)" in text
    assert "Session:</b> Pre-market" in text
    assert "Nov 10, 8:15 AM ET" in text


def test_format_quote_after_hours():
    tz = zoneinfo.ZoneInfo("America/New_York")
    ref_now = datetime.datetime(2026, 11, 10, 17, 30, tzinfo=tz)
    reg_time = int(datetime.datetime(2026, 11, 10, 16, 0, tzinfo=tz).timestamp())
    post_time = int(datetime.datetime(2026, 11, 10, 17, 15, tzinfo=tz).timestamp())
    q = {
        "symbol": "AAPL",
        "price": 250.0,
        "previous": 248.5,
        "open": 249.0,
        "meta": {
            "currency": "USD",
            "shortName": "Apple Inc.",
            "marketState": "POST",
            "postMarketPrice": 251.25,
            "postMarketChange": 1.25,
            "postMarketChangePercent": 0.50,
            "regularMarketTime": reg_time,
            "postMarketTime": post_time,
        },
    }
    text = format_quote(q, crypto=False, now_dt=ref_now)
    assert "Apple Inc. (AAPL)" in text
    assert "Regular Close:</b> $250.00" in text
    assert "🌙 <b>After-Hours:</b> $251.25" in text
    assert "+$1.25" in text
    assert "(+0.50%)" in text
    assert "Session:</b> After-hours" in text
    assert "Nov 10, 5:15 PM ET" in text


def test_format_quote_crypto():
    q = {
        "symbol": "BTC-USD",
        "price": 60000.0,
        "previous": 58000.0,
        "meta": {
            "currency": "USD",
            "shortName": "Bitcoin USD",
            "marketState": "REGULAR",
        },
    }
    text = format_quote(q, crypto=True)
    assert "🪙 <b>Bitcoin USD (BTC/USD)</b>" in text
    assert "$60,000.00" in text
    assert "24/7 continuous trading" in text
    assert "Pre-Market" not in text
    assert "After-Hours" not in text


@pytest.mark.asyncio
async def test_retired_commands_notice():
    env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123:TOKEN",
        "TELEGRAM_WEBHOOK_SECRET": "secret_token",
    }
    dummy_msg = {"chat": {"id": 123}, "from": {"id": 456}}

    reply_alert = await reply_for("alert", ["add", "AAPL", "above", "150"], dummy_msg, env)
    assert "retired" in reply_alert.lower()
    assert "stateless" in reply_alert.lower()

    reply_watchlist = await reply_for("watchlist", ["add", "AAPL"], dummy_msg, env)
    assert "retired" in reply_watchlist.lower()
    assert "stateless" in reply_watchlist.lower()


@pytest.mark.asyncio
async def test_handle_request_health():
    req = MockRequest(method="GET", url="https://example.com/health")
    resp = await handle_request(req, {})
    assert resp.status == 200
    assert json.loads(resp.body) == {"ok": True}


@pytest.mark.asyncio
async def test_handle_request_secret_verification(monkeypatch):
    env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123:TOKEN",
        "TELEGRAM_WEBHOOK_SECRET": "secret_token_123",
    }
    monkeypatch.setattr("cloudflare.webhook.telegram", AsyncMock(return_value={"username": "testbot"}))

    # Missing secret token -> 403
    req_missing = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={},
        body=json.dumps({"update_id": 1, "message": {"text": "/stock AAPL", "chat": {"id": 123}}}),
    )
    resp = await handle_request(req_missing, env)
    assert resp.status == 403

    # Valid secret token -> 200
    req_ok = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret_token_123"},
        body=json.dumps({"update_id": 1, "message": {"text": "/help", "chat": {"id": 123}}}),
    )
    resp_ok = await handle_request(req_ok, env)
    assert resp_ok.status == 200


@pytest.mark.asyncio
async def test_handle_request_in_memory_deduplication(monkeypatch):
    env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123:TOKEN",
        "TELEGRAM_WEBHOOK_SECRET": "secret_token_123",
    }
    monkeypatch.setattr("cloudflare.webhook.telegram", AsyncMock(return_value={"username": "testbot"}))

    payload = json.dumps({"update_id": 9999, "message": {"text": "/help", "chat": {"id": 123}}})
    req1 = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret_token_123"},
        body=payload,
    )
    resp1 = await handle_request(req1, env)
    assert resp1.status == 200

    # Second delivery with the same update_id -> suppressed as duplicate
    req2 = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret_token_123"},
        body=payload,
    )
    resp2 = await handle_request(req2, env)
    assert resp2.status == 200
    data = json.loads(resp2.body)
    assert data.get("duplicate") is True


@pytest.mark.asyncio
async def test_handle_request_edited_message(monkeypatch):
    env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123:TOKEN",
        "TELEGRAM_WEBHOOK_SECRET": "secret_token_123",
    }
    monkeypatch.setattr("cloudflare.webhook.telegram", AsyncMock(return_value={"username": "testbot"}))
    payload = json.dumps({"update_id": 8888, "edited_message": {"text": "/help", "chat": {"id": 123}}})
    req = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret_token_123"},
        body=payload,
    )
    resp = await handle_request(req, env)
    assert resp.status == 200


@pytest.mark.asyncio
async def test_handle_request_group_bot_mention(monkeypatch):
    env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123:TOKEN",
        "TELEGRAM_WEBHOOK_SECRET": "secret_token_123",
    }
    monkeypatch.setattr("cloudflare.webhook.telegram", AsyncMock(return_value={"username": "financebot"}))

    # Mention matching our bot -> processed
    req_match = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret_token_123"},
        body=json.dumps({"update_id": 101, "message": {"text": "/help@financebot", "chat": {"id": 123}}}),
    )
    resp_match = await handle_request(req_match, env)
    assert resp_match.status == 200

    # Mention targeting a different bot -> ignored
    req_other = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret_token_123"},
        body=json.dumps({"update_id": 102, "message": {"text": "/help@otherbot", "chat": {"id": 123}}}),
    )
    resp_other = await handle_request(req_other, env)
    assert resp_other.status == 200


@pytest.mark.asyncio
async def test_handle_request_payload_too_large():
    env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123:TOKEN",
        "TELEGRAM_WEBHOOK_SECRET": "secret_token_123",
    }
    big_body = "x" * (1048576 + 50)
    req = MockRequest(
        method="POST",
        url="https://example.com/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret_token_123", "content-length": str(len(big_body))},
        body=big_body,
    )
    resp = await handle_request(req, env)
    assert resp.status == 413


@pytest.mark.asyncio
async def test_cloudflare_all_core_commands(monkeypatch):
    env = {
        "BOT_MODE": "webhook",
        "TELEGRAM_BOT_TOKEN": "123:TOKEN",
        "TELEGRAM_WEBHOOK_SECRET": "secret_token_123",
        "ADMIN_USER_IDS": "777",
    }
    dummy_msg = {"chat": {"id": 123}, "from": {"id": 777}}

    async def mock_data_req(path, params, ttl=45):
        if "chart" in path:
            return {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "regularMarketPrice": 150.0,
                                "previousClose": 148.0,
                                "currency": "USD",
                                "shortName": "Apple Inc.",
                                "marketState": "REGULAR",
                            },
                            "indicators": {"quote": [{"close": [148.0, 150.0]}]},
                            "timestamp": [1700000000, 1700086400],
                        }
                    ]
                }
            }
        if "search" in path:
            return {
                "quotes": [{"symbol": "AAPL", "shortname": "Apple Inc.", "exchDisp": "NASDAQ", "quoteType": "EQUITY"}],
                "news": [{"title": "Apple Announcement", "link": "https://example.com/news"}],
            }
        return {}

    monkeypatch.setattr("cloudflare.webhook.data_request", mock_data_req)
    monkeypatch.setattr(
        "cloudflare.webhook.company_summary",
        AsyncMock(
            return_value={
                "price": {"shortName": "Apple Inc.", "marketCap": {"raw": 3000000000000}},
                "assetProfile": {
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                    "website": "https://apple.com",
                },
                "summaryDetail": {"trailingPE": {"raw": 30.5}},
            }
        ),
    )

    # /stock
    res_stock = await reply_for("stock", ["AAPL"], dummy_msg, env)
    assert "Apple Inc." in res_stock
    assert "$150.00" in res_stock

    # /indices (cash + futures)
    res_indices = await reply_for("indices", [], dummy_msg, env)
    assert "Major Market Indices (Cash)" in res_indices
    assert "S&amp;P 500" in res_indices
    assert "Market Futures" in res_indices

    # /compare
    res_compare = await reply_for("compare", ["AAPL", "MSFT"], dummy_msg, env)
    assert "AAPL" in res_compare
    assert "MSFT" in res_compare

    # /chart
    res_chart = await reply_for("chart", ["AAPL"], dummy_msg, env)
    assert isinstance(res_chart, dict)
    assert res_chart["image"].startswith(b"\x89PNG")

    # /search
    res_search = await reply_for("search", ["Apple"], dummy_msg, env)
    assert "AAPL" in res_search

    # /stocknews
    res_news = await reply_for("stocknews", ["AAPL"], dummy_msg, env)
    assert "Apple Announcement" in res_news

    # /marketcap
    res_mcap = await reply_for("marketcap", ["AAPL"], dummy_msg, env)
    assert "Market Cap:" in res_mcap
    assert "3.00T" in res_mcap

    # /stockinfo
    res_info = await reply_for("stockinfo", ["AAPL"], dummy_msg, env)
    assert "Technology" in res_info
    assert "https://apple.com" in res_info

    # /admin stats
    res_admin = await reply_for("admin", ["stats"], dummy_msg, env)
    assert "Admin Stats" in res_admin
    assert "Cloudflare Python Worker" in res_admin


def test_worker_pre_market_missing_timestamp_rejected():
    tz = zoneinfo.ZoneInfo("America/New_York")
    ref_now = datetime.datetime(2026, 11, 10, 8, 30, tzinfo=tz)
    q = {
        "symbol": "AAPL",
        "price": 250.0,
        "previous": 248.5,
        "meta": {
            "currency": "USD",
            "shortName": "Apple Inc.",
            "marketState": "PRE",
            "preMarketPrice": 252.15,
            "preMarketTime": None,  # Missing timestamp
        },
    }
    text = format_quote(q, crypto=False, now_dt=ref_now)
    assert "Session:</b> Closed" in text
    assert "🌅 <b>Pre-Market:</b>" not in text


def test_worker_pre_market_friday_timestamp_on_monday_rejected():
    tz = zoneinfo.ZoneInfo("America/New_York")
    monday = datetime.datetime(2026, 11, 9, 8, 30, tzinfo=tz)
    friday_pre_time = int(datetime.datetime(2026, 11, 6, 8, 15, tzinfo=tz).timestamp())
    friday_reg_time = int(datetime.datetime(2026, 11, 6, 16, 0, tzinfo=tz).timestamp())

    q = {
        "symbol": "AAPL",
        "price": 250.0,
        "previous": 248.5,
        "meta": {
            "currency": "USD",
            "shortName": "Apple Inc.",
            "marketState": "PRE",
            "preMarketPrice": 252.15,
            "regularMarketTime": friday_reg_time,
            "preMarketTime": friday_pre_time,  # Old Friday pre-market trade
        },
    }
    text = format_quote(q, crypto=False, now_dt=monday)
    assert "Session:</b> Closed" in text
    assert "🌅 <b>Pre-Market:</b>" not in text


def test_worker_bounded_cache_eviction():
    import time
    from collections import OrderedDict

    cache = OrderedDict()
    # Insert 3 entries with max_size=2
    _cache_set(cache, "k1", (time.time() + 100, {"v": 1}), max_size=2)
    _cache_set(cache, "k2", (time.time() + 100, {"v": 2}), max_size=2)
    assert len(cache) == 2
    assert _cache_get(cache, "k1") == {"v": 1}

    # k1 accessed, so k2 is now oldest. Adding k3 should evict k2.
    _cache_set(cache, "k3", (time.time() + 100, {"v": 3}), max_size=2)
    assert len(cache) == 2
    assert "k2" not in cache
    assert _cache_get(cache, "k1") == {"v": 1}
    assert _cache_get(cache, "k3") == {"v": 3}


@pytest.mark.asyncio
async def test_worker_timed_fetch_timeout(monkeypatch):
    import asyncio

    async def hanging_fetch(_url, _opts):
        await asyncio.sleep(1.0)
        return None

    monkeypatch.setattr("cloudflare.webhook.cf_fetch", hanging_fetch)
    with pytest.raises(RuntimeError, match="HTTP fetch timed out"):
        await timed_fetch("https://example.com", timeout=0.01)


@pytest.mark.asyncio
async def test_worker_quote_parses_intraday_bars(monkeypatch):
    # Verify that quote parses intraday 5m bars to extract pre/post market trade prices and open
    chart_payload = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "currency": "USD",
                        "symbol": "TEST",
                        "regularMarketPrice": 105.0,
                        "chartPreviousClose": 100.0,
                        "currentTradingPeriod": {
                            "pre": {"start": 1000, "end": 2000},
                            "regular": {"start": 2000, "end": 3000},
                            "post": {"start": 3000, "end": 4000},
                        },
                    },
                    "timestamp": [1500, 2100, 3500],
                    "indicators": {
                        "quote": [
                            {
                                "open": [101.0, 103.0, 106.0],
                                "close": [102.5, 105.0, 107.5],
                                "high": [103.0, 106.0, 108.0],
                                "low": [100.0, 102.0, 105.0],
                            }
                        ]
                    },
                }
            ]
        }
    }

    async def mock_data_request(_path, _params, ttl=45):
        return chart_payload

    monkeypatch.setattr("cloudflare.webhook.data_request", mock_data_request)
    # Clear QUOTE_CACHE
    from cloudflare.webhook import QUOTE_CACHE

    QUOTE_CACHE.clear()

    res = await quote({}, "TEST")
    assert res["price"] == 105.0
    assert res["previous"] == 100.0
    assert res["open"] == 103.0  # Regular session open
    assert res["preMarketPrice"] == 102.5  # Pre-market bar close
    assert res["preMarketTime"] == 1500
    assert res["postMarketPrice"] == 107.5  # Post-market bar close
    assert res["postMarketTime"] == 3500
