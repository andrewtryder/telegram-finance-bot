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


@pytest.mark.asyncio
async def test_concurrent_updates_do_not_block_each_other():
    # Verify that slow updates do not hold a global lock preventing other updates from proceeding
    import asyncio

    completion_order = []

    async def slow_process(update):
        if update.update_id == 1:
            await asyncio.sleep(0.12)
            completion_order.append(1)
        elif update.update_id == 2:
            await asyncio.sleep(0.02)
            completion_order.append(2)

    application = MagicMock()
    application.process_update = AsyncMock(side_effect=slow_process)

    async with TestClient(TestServer(create_server(application, "secret"))) as client:
        headers = {"X-Telegram-Bot-Api-Secret-Token": "secret"}
        task1 = client.post("/webhook", json={"update_id": 1}, headers=headers)
        task2 = client.post("/webhook", json={"update_id": 2}, headers=headers)

        res1, res2 = await asyncio.gather(task1, task2)
        assert res1.status == 200
        assert res2.status == 200
        # Update 2 had shorter delay, so it should finish before update 1
        assert completion_order == [2, 1]


@pytest.mark.asyncio
async def test_concurrent_duplicate_awaits_primary_failure():
    # If a duplicate arrives while primary is in-flight, and primary fails,
    # the duplicate must NOT be acknowledged with 200 (which would lose the update).
    # Both must return 503 so Telegram retries.
    import asyncio

    async def failing_process(_update):
        await asyncio.sleep(0.05)
        raise RuntimeError("database/provider down")

    application = MagicMock()
    application.process_update = AsyncMock(side_effect=failing_process)

    async with TestClient(TestServer(create_server(application, "secret"))) as client:
        headers = {"X-Telegram-Bot-Api-Secret-Token": "secret"}
        task1 = client.post("/webhook", json={"update_id": 99}, headers=headers)
        task2 = client.post("/webhook", json={"update_id": 99}, headers=headers)

        res1, res2 = await asyncio.gather(task1, task2)
        assert res1.status == 503
        assert res2.status == 503

        # Subsequent retry succeeds
        application.process_update = AsyncMock(return_value=None)
        res_retry = await client.post("/webhook", json={"update_id": 99}, headers=headers)
        assert res_retry.status == 200

        # Now that it succeeded, subsequent duplicate returns 200 duplicate
        res_dup = await client.post("/webhook", json={"update_id": 99}, headers=headers)
        assert res_dup.status == 200
        assert (await res_dup.json())["duplicate"] is True


@pytest.mark.asyncio
async def test_concurrent_duplicate_awaits_primary_success():
    # If a duplicate arrives while primary is in-flight, and primary succeeds,
    # the duplicate waits and safely returns 200 duplicate.
    import asyncio

    async def slow_success(_update):
        await asyncio.sleep(0.05)
        return None

    application = MagicMock()
    application.process_update = AsyncMock(side_effect=slow_success)

    async with TestClient(TestServer(create_server(application, "secret"))) as client:
        headers = {"X-Telegram-Bot-Api-Secret-Token": "secret"}
        task1 = client.post("/webhook", json={"update_id": 101}, headers=headers)
        task2 = client.post("/webhook", json={"update_id": 101}, headers=headers)

        res1, res2 = await asyncio.gather(task1, task2)
        assert res1.status == 200
        assert res2.status == 200
        # Exactly one is duplicate
        data1 = await res1.json()
        data2 = await res2.json()
        assert (data1.get("duplicate") is True) != (data2.get("duplicate") is True)
