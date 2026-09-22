"""
Unit tests for Telegram Notifier module in Deriv Crypto AI Bot.
"""

from unittest.mock import patch, MagicMock
import pytest
from src.utils.telegram_notifier import TelegramNotifier


def test_telegram_disabled_when_missing_tokens():
    notifier = TelegramNotifier(bot_token="", chat_id="")
    assert notifier.enabled is False
    assert notifier.send_message("Test message") is False


@patch("urllib.request.urlopen")
def test_telegram_send_message_success(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"ok": true, "result": {"message_id": 123}}'
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    notifier = TelegramNotifier(bot_token="fake_token", chat_id="123456")
    assert notifier.enabled is True
    res = notifier.send_message("Test hello world")
    assert res is True


@patch("urllib.request.urlopen")
def test_telegram_notify_startup(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"ok": true, "result": {"message_id": 123}}'
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    notifier = TelegramNotifier(bot_token="fake_token", chat_id="123456")
    res = notifier.notify_startup(active_symbols=["cryBTCUSD", "cryETHUSD"], config_hash="b3c246f9b22b")
    assert res is True


@patch("urllib.request.urlopen")
def test_telegram_notify_paper_trade(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"ok": true, "result": {"message_id": 124}}'
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    notifier = TelegramNotifier(bot_token="fake_token", chat_id="123456")
    res = notifier.notify_paper_trade(
        record_id="rec_123",
        symbol="cryBTCUSD",
        direction="BULLISH",
        contract_type="CALL",
        stake=15.0,
        payout=30.0,
        score=58.5,
        ev=2.40,
    )
    assert res is True
