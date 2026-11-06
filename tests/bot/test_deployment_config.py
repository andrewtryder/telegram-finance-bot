from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from bot import config
from bot.main import post_init
from bot.webhook import create_server


def test_valid_bot_modes():
    config.BOT_MODE = "polling"
    config.validate_config()
    config.BOT_MODE = "webhook"
    config.validate_config()


def test_invalid_bot_mode_rejected(monkeypatch):
    monkeypatch.setattr(config, "BOT_MODE", "invalid_mode")
    with pytest.raises(ValueError, match="BOT_MODE must be polling or webhook"):
        config.validate_config()


@pytest.mark.asyncio
async def test_polling_refuses_active_webhook():
    application = MagicMock()
    application.bot.get_webhook_info = AsyncMock(return_value=MagicMock(url="https://example.com/webhook"))
    with pytest.raises(RuntimeError, match="webhook is active"):
        await post_init(application)


@pytest.mark.asyncio
async def test_python_webhook_health_endpoint():
    application = MagicMock()
    server = create_server(application, "valid_secret_12345")
    async with TestClient(TestServer(server)) as client:
        response = await client.get("/health")
        assert response.status == 200
        assert await response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_python_webhook_secret_verification():
    application = MagicMock()
    application.process_update = AsyncMock()
    server = create_server(application, "my_secret_token_abc")
    async with TestClient(TestServer(server)) as client:
        # Missing secret header -> 403
        resp_no_header = await client.post("/webhook", json={"update_id": 1, "message": {"text": "/stock AAPL"}})
        assert resp_no_header.status == 403

        # Incorrect secret header -> 403
        resp_bad_header = await client.post(
            "/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_secret"},
            json={"update_id": 1, "message": {"text": "/stock AAPL"}},
        )
        assert resp_bad_header.status == 403

        # Correct secret header -> 200
        resp_ok = await client.post(
            "/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "my_secret_token_abc"},
            json={"update_id": 1},
        )
        assert resp_ok.status == 200
        assert await resp_ok.json() == {"ok": True}
