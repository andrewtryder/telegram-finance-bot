from unittest.mock import MagicMock, patch

from bot import config


def test_init_honeybadger_disabled_without_key(monkeypatch):
    monkeypatch.setattr(config, "HONEYBADGER_API_KEY", None)
    assert config.init_honeybadger() is False


def test_init_honeybadger_configures_client(monkeypatch):
    monkeypatch.setattr(config, "HONEYBADGER_API_KEY", "test-key")
    monkeypatch.setattr(config, "HONEYBADGER_ENVIRONMENT", "test")
    mock_hb = MagicMock()
    with patch.dict("sys.modules", {"honeybadger": MagicMock(honeybadger=mock_hb)}):
        # Re-import path used inside init: from honeybadger import honeybadger
        with patch("honeybadger.honeybadger", mock_hb):
            assert config.init_honeybadger() is True
            mock_hb.configure.assert_called_once_with(api_key="test-key", environment="test")


def test_notify_honeybadger_noop_without_key(monkeypatch):
    monkeypatch.setattr(config, "HONEYBADGER_API_KEY", None)
    config.notify_honeybadger(ValueError("x"), chat_id=1)


def test_notify_honeybadger_sends_exception(monkeypatch):
    monkeypatch.setattr(config, "HONEYBADGER_API_KEY", "test-key")
    mock_hb = MagicMock()
    err = RuntimeError("boom")
    with patch("honeybadger.honeybadger", mock_hb):
        config.notify_honeybadger(err, chat_id=42)
        mock_hb.notify.assert_called_once_with(err, context={"chat_id": 42})
