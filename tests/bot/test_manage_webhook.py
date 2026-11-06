from unittest.mock import MagicMock

import pytest

from bot.manage_webhook import run


def test_register_webhook_uses_secret_and_preserves_pending_updates():
    client = MagicMock()
    client.post.return_value.json.return_value = {"ok": True}
    env = {
        "TELEGRAM_BOT_TOKEN": "123:test",
        "TELEGRAM_WEBHOOK_SECRET": "secret",
        "WEBHOOK_URL": "https://example.com/webhook",
    }
    run("register", env, client)
    assert client.post.call_args.kwargs["json"] == {
        "url": env["WEBHOOK_URL"],
        "secret_token": "secret",
        "drop_pending_updates": False,
    }


def test_rejects_insecure_url_without_contacting_telegram():
    client = MagicMock()
    with pytest.raises(ValueError):
        run(
            "register",
            {
                "TELEGRAM_BOT_TOKEN": "123:test",
                "TELEGRAM_WEBHOOK_SECRET": "secret",
                "WEBHOOK_URL": "http://example.com",
            },
            client,
        )
    client.post.assert_not_called()


def test_remove_and_info_use_correct_methods():
    client = MagicMock()
    client.post.return_value.json.return_value = {"ok": True, "result": {}}
    run("remove", {"TELEGRAM_BOT_TOKEN": "123:test"}, client)
    assert client.post.call_args.args[0].endswith("/deleteWebhook")
    run("info", {"TELEGRAM_BOT_TOKEN": "123:test"}, client)
    assert client.post.call_args.args[0].endswith("/getWebhookInfo")
