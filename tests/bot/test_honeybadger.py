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


def test_notify_honeybadger_skips_network_timeout(monkeypatch):
    from telegram.error import TimedOut

    monkeypatch.setattr(config, "HONEYBADGER_API_KEY", "test-key")
    mock_hb = MagicMock()
    err = TimedOut("Timed out")
    with patch("honeybadger.honeybadger", mock_hb):
        config.notify_honeybadger(err, chat_id=42)
        mock_hb.notify.assert_not_called()


def test_is_network_timeout_variants():
    import httpx
    from telegram.error import NetworkError, TimedOut

    class NetworkTimeout(Exception):
        pass

    assert config.is_network_timeout(None) is False
    assert config.is_network_timeout(TimedOut("Timed out")) is True
    assert config.is_network_timeout(NetworkError("httpx.ConnectTimeout: Connection timed out")) is True
    assert config.is_network_timeout(NetworkTimeout("timed out")) is True
    assert config.is_network_timeout(httpx.ReadTimeout("Read timed out")) is True
    assert config.is_network_timeout(httpx.PoolTimeout("Pool timeout")) is True
    assert config.is_network_timeout(TimeoutError("Operation timed out")) is True

    # Chained exception
    wrapper = RuntimeError("Handler failure")
    wrapper.__cause__ = TimedOut("Timed out")
    assert config.is_network_timeout(wrapper) is True

    # Normal application exceptions
    assert config.is_network_timeout(ValueError("bad value")) is False
    assert config.is_network_timeout(RuntimeError("something else")) is False
