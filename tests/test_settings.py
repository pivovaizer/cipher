import os
from unittest.mock import patch

import pytest

from config.settings import Settings


def _env(**overrides):
    """Base valid environment + overrides."""
    base = {
        "BINANCE_API_KEY": "key",
        "BINANCE_API_SECRET": "secret",
        "INVESTMENT_AMOUNT": "10",
        "LEVERAGE": "20",
        "STRATEGY_ENABLED": "false",
    }
    base.update(overrides)
    return base


class TestSettings:
    @patch.dict(os.environ, _env(), clear=False)
    def test_defaults(self):
        s = Settings()
        assert s.INVESTMENT_AMOUNT == 10.0
        assert s.LEVERAGE == 20
        assert s.STRATEGY_ENABLED is False

    @patch.dict(os.environ, _env(INVESTMENT_AMOUNT="0"), clear=False)
    def test_invalid_investment_amount(self):
        with pytest.raises(ValueError, match="INVESTMENT_AMOUNT"):
            Settings()

    @patch.dict(os.environ, _env(LEVERAGE="200"), clear=False)
    def test_invalid_leverage(self):
        with pytest.raises(ValueError, match="LEVERAGE"):
            Settings()

    @patch.dict(os.environ, _env(LEVERAGE="0"), clear=False)
    def test_leverage_too_low(self):
        with pytest.raises(ValueError, match="LEVERAGE"):
            Settings()

    @patch.dict(os.environ, _env(
        STRATEGY_ENABLED="true",
        STRATEGY_SYMBOLS="BTCUSDT,ETHUSDT",
        STRATEGY_TIMEFRAME="15m",
        STRATEGY_LEVERAGE="10",
    ), clear=False)
    def test_strategy_enabled(self):
        s = Settings()
        assert s.STRATEGY_ENABLED is True
        assert s.STRATEGY_SYMBOLS == ["BTCUSDT", "ETHUSDT"]

    @patch.dict(os.environ, _env(
        STRATEGY_ENABLED="true",
        STRATEGY_SYMBOLS="",
        STRATEGY_TIMEFRAME="15m",
        STRATEGY_LEVERAGE="10",
    ), clear=False)
    def test_strategy_no_symbols(self):
        with pytest.raises(ValueError, match="STRATEGY_SYMBOLS"):
            Settings()

    @patch.dict(os.environ, _env(
        STRATEGY_ENABLED="true",
        STRATEGY_SYMBOLS="BTCUSDT",
        STRATEGY_TIMEFRAME="7m",
        STRATEGY_LEVERAGE="10",
    ), clear=False)
    def test_strategy_invalid_timeframe(self):
        with pytest.raises(ValueError, match="STRATEGY_TIMEFRAME"):
            Settings()

    @patch.dict(os.environ, _env(
        STRATEGY_ENABLED="true",
        STRATEGY_SYMBOLS="BTCUSDT",
        STRATEGY_TIMEFRAME="15m",
        STRATEGY_LEVERAGE="100",
    ), clear=False)
    def test_strategy_leverage_too_high(self):
        with pytest.raises(ValueError, match="STRATEGY_LEVERAGE"):
            Settings()

    @patch.dict(os.environ, _env(
        STRATEGY_ENABLED="true",
        STRATEGY_SYMBOLS="BTCUSDT",
        STRATEGY_TIMEFRAME="15m",
        STRATEGY_LEVERAGE="10",
        RISK_PER_TRADE_PERCENT="10",
    ), clear=False)
    def test_risk_per_trade_too_high(self):
        with pytest.raises(ValueError, match="RISK_PER_TRADE_PERCENT"):
            Settings()

    @patch.dict(os.environ, _env(SIGNAL_MAX_DELAY_MINUTES="0"), clear=False)
    def test_invalid_signal_delay(self):
        with pytest.raises(ValueError, match="SIGNAL_MAX_DELAY_MINUTES"):
            Settings()

    @patch.dict(os.environ, _env(
        STRATEGY_SYMBOLS="  BTCUSDT , ETHUSDT , SOLUSDT  ",
        STRATEGY_ENABLED="false",
    ), clear=False)
    def test_symbols_trimmed(self):
        s = Settings()
        assert s.STRATEGY_SYMBOLS == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
