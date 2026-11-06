import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer
from telegram.ext import ApplicationBuilder
from telegram.request import BaseRequest

from bot.main import register_handlers
from bot.webhook import create_server


@pytest.mark.asyncio
async def test_webhook_authentication_processing_and_duplicate():
    application = MagicMock()
    application.process_update = AsyncMock()
    async with TestClient(TestServer(create_server(application, "secret"))) as client:
        assert (await client.get("/health")).status == 200
        assert (await client.post("/webhook", json={"update_id": 42})).status == 403
        headers = {"X-Telegram-Bot-Api-Secret-Token": "secret"}
        assert (await client.post("/webhook", json={}, headers=headers)).status == 400
        assert (await client.post("/webhook", json={"update_id": 42}, headers=headers)).status == 200
        duplicate = await client.post("/webhook", json={"update_id": 42}, headers=headers)
        assert (await duplicate.json())["duplicate"]
        application.process_update.assert_awaited_once()
        assert application.process_update.await_args.args[0].update_id == 42


@pytest.mark.asyncio
async def test_failed_update_can_be_retried():
    application = MagicMock()
    application.process_update = AsyncMock(side_effect=[RuntimeError("failed"), None])
    async with TestClient(TestServer(create_server(application, "secret"))) as client:
        headers = {"X-Telegram-Bot-Api-Secret-Token": "secret"}
        assert (await client.post("/webhook", json={"update_id": 7}, headers=headers)).status == 503
        assert (await client.post("/webhook", json={"update_id": 7}, headers=headers)).status == 200


@pytest.mark.asyncio
async def test_start_routes_through_existing_handlers(monkeypatch):
    monkeypatch.setattr("bot.utils.ALLOWED_CHAT_IDS", set())

    class TelegramStub(BaseRequest):
        read_timeout = 5

        def __init__(self):
            self.messages = []

        async def initialize(self):
            pass

        async def shutdown(self):
            pass

        async def do_request(self, url, method, request_data=None, **kwargs):
            name = url.rsplit("/", 1)[-1]
            if name == "getMe":
                result = {"id": 123, "is_bot": True, "first_name": "Bot", "username": "test_bot"}
            elif name == "sendMessage":
                self.messages.append(request_data.parameters["text"])
                result = {"message_id": 1, "date": 0, "chat": {"id": 17, "type": "private"}, "text": "ok"}
            else:
                result = True
            return 200, json.dumps({"ok": True, "result": result}).encode()

    stub = TelegramStub()
    application = ApplicationBuilder().token("123:dummy").request(stub).build()
    register_handlers(application)
    await application.initialize()
    try:
        async with TestClient(TestServer(create_server(application, "secret"))) as client:
            payload = {
                "update_id": 88,
                "message": {
                    "message_id": 1,
                    "date": 0,
                    "chat": {"id": 17, "type": "private"},
                    "from": {"id": 17, "is_bot": False, "first_name": "Test"},
                    "text": "/start",
                    "entities": [{"type": "bot_command", "offset": 0, "length": 6}],
                },
            }
            response = await client.post(
                "/webhook", json=payload, headers={"X-Telegram-Bot-Api-Secret-Token": "secret"}
            )
            assert response.status == 200
            assert "Financial Market Bot" in stub.messages[0]
    finally:
        await application.shutdown()
