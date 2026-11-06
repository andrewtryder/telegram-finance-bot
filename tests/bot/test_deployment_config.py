import importlib
import sqlite3
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot import config, storage
from bot.main import post_init


@pytest.mark.parametrize(
    "watchlists,alerts,expected",
    [(False, False, set()), (True, False, {"watchlist"}), (False, True, {"alerts"})],
)
def test_storage_creates_only_enabled_tables(tmp_path, monkeypatch, watchlists, alerts, expected):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "WATCHLIST_ENABLED", watchlists)
    monkeypatch.setattr(config, "ALERTS_ENABLED", alerts)
    monkeypatch.setattr(storage, "_db_path", None)
    storage.init_storage()
    database = tmp_path / "bot.db"
    if not expected:
        assert not database.exists()
        return
    with sqlite3.connect(database) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables & {"watchlist", "alerts"} == expected


def test_none_backend_requires_features_disabled(monkeypatch):
    monkeypatch.setattr(config, "BOT_MODE", "polling")
    monkeypatch.setattr(config, "STORAGE_BACKEND", "none")
    monkeypatch.setattr(config, "WATCHLIST_ENABLED", True)
    monkeypatch.setattr(config, "ALERTS_ENABLED", False)
    with pytest.raises(ValueError, match="require persistent storage"):
        config.validate_config()
    monkeypatch.setattr(config, "WATCHLIST_ENABLED", False)
    config.validate_config()


def test_d1_backend_rejected_in_python_runtime(monkeypatch):
    monkeypatch.setattr(config, "BOT_MODE", "polling")
    monkeypatch.setattr(config, "STORAGE_BACKEND", "d1")
    monkeypatch.setattr(config, "WATCHLIST_ENABLED", False)
    monkeypatch.setattr(config, "ALERTS_ENABLED", False)
    with pytest.raises(ValueError, match="D1 storage is only supported on Cloudflare Workers"):
        config.validate_config()


def test_invalid_bot_mode_rejected(monkeypatch):
    monkeypatch.setattr(config, "BOT_MODE", "invalid_mode")
    with pytest.raises(ValueError, match="BOT_MODE must be polling or webhook"):
        config.validate_config()


def test_invalid_storage_backend_rejected(monkeypatch):
    monkeypatch.setattr(config, "STORAGE_BACKEND", "redis")
    with pytest.raises(ValueError, match="STORAGE_BACKEND must be none, sqlite, or d1"):
        config.validate_config()


@pytest.mark.asyncio
async def test_polling_refuses_active_webhook():
    application = MagicMock()
    application.bot.get_webhook_info = AsyncMock(return_value=MagicMock(url="https://example.com/webhook"))
    with pytest.raises(RuntimeError, match="webhook is active"):
        await post_init(application)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module_name,flag,command,storage_function,reply",
    [
        ("bot.commands.watchlist", "WATCHLIST_ENABLED", "watchlist", "watchlist_list", "Watchlists are disabled"),
        ("bot.commands.alerts", "ALERTS_ENABLED", "alert", "alert_list", "Price alerts are disabled"),
    ],
)
async def test_disabled_commands_do_not_access_storage(
    monkeypatch, module_name, flag, command, storage_function, reply
):
    module = importlib.import_module(module_name)
    monkeypatch.setattr(module, flag, False)
    storage_call = MagicMock(side_effect=AssertionError("storage must not be called"))
    monkeypatch.setattr(module, storage_function, storage_call)
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock(effective_message=message, effective_chat=None, effective_user=None)
    context = MagicMock()
    context.bot.send_chat_action = AsyncMock()
    await getattr(module, command)(update, context)
    assert reply in message.reply_text.await_args.args[0]
    storage_call.assert_not_called()


@pytest.mark.asyncio
async def test_stateless_polling_skips_storage(monkeypatch):
    main_module = importlib.import_module("bot.main")
    monkeypatch.setattr(main_module, "STORAGE_BACKEND", "none")
    monkeypatch.setattr(main_module, "ALERTS_ENABLED", False)
    init_storage = MagicMock(side_effect=AssertionError("storage must not be initialized"))
    monkeypatch.setattr(main_module, "init_storage", init_storage)
    monkeypatch.setattr(main_module, "setup_commands", AsyncMock())
    application = MagicMock(job_queue=None)
    application.bot.get_webhook_info = AsyncMock(return_value=MagicMock(url=""))
    await post_init(application)
    init_storage.assert_not_called()
