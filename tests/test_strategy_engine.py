import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from services.strategy_engine import StrategyEngine

pytestmark = pytest.mark.asyncio


@pytest.fixture
def engine():
    order_manager = MagicMock()
    position_service = MagicMock()
    position_store = MagicMock()
    position_store.get_open_positions.return_value = []
    return StrategyEngine(order_manager, position_service, position_store)


# ── _seconds_until_next_candle ─────────────────────────────────


class TestSecondsUntilNextCandle:
    @patch("services.strategy_engine.settings")
    def test_15m_timeframe(self, mock_settings, engine):
        mock_settings.STRATEGY_TIMEFRAME = "15m"
        result = engine._seconds_until_next_candle()
        assert isinstance(result, int)
        assert result >= 1

    @patch("services.strategy_engine.settings")
    def test_1h_timeframe(self, mock_settings, engine):
        mock_settings.STRATEGY_TIMEFRAME = "1h"
        result = engine._seconds_until_next_candle()
        assert isinstance(result, int)
        assert result >= 1

    @patch("services.strategy_engine.settings")
    def test_unknown_timeframe_defaults(self, mock_settings, engine):
        mock_settings.STRATEGY_TIMEFRAME = "1d"
        result = engine._seconds_until_next_candle()
        assert result >= 1


# ── _evaluate_symbol ───────────────────────────────────────────


def _make_df(n=600, signal_type=None):
    """Create a DataFrame with NW indicators pre-calculated."""
    close = np.linspace(100, 110, n).copy()
    high = close + 2
    low = close - 2

    nw_line = close.copy()
    nw_upper = close + 5
    nw_lower = close - 5

    if signal_type == "long":
        # Last completed candle (iloc[-2]) closes below lower band
        close[-2] = nw_lower[-2] - 1
        low[-2] = nw_lower[-2] - 2
        high[-2] = nw_lower[-2] - 0.5
    elif signal_type == "short":
        # Last completed candle (iloc[-2]) closes above upper band
        close[-2] = nw_upper[-2] + 1
        high[-2] = nw_upper[-2] + 2
        low[-2] = nw_upper[-2] + 0.5

    df = pd.DataFrame({
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "volume": np.ones(n) * 1000,
        "open_time": pd.date_range("2026-01-01", periods=n, freq="15min"),
        "nw_line": nw_line,
        "nw_upper": nw_upper,
        "nw_lower": nw_lower,
    })
    return df


def _patch_asyncio_to_thread():
    """Make asyncio.to_thread run synchronously in tests."""
    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)
    return patch("asyncio.to_thread", side_effect=fake_to_thread)


class TestEvaluateSymbol:
    async def test_long_signal(self, engine):
        with (
            _patch_asyncio_to_thread(),
            patch("services.strategy_engine.calculate_nadaraya_watson") as mock_nw,
            patch("services.strategy_engine.klines_to_dataframe") as mock_klines,
            patch("services.strategy_engine.binance_gateway") as mock_gw,
            patch("services.strategy_engine.settings") as mock_settings,
        ):
            mock_settings.STRATEGY_TIMEFRAME = "15m"
            mock_settings.STRATEGY_KLINES_LIMIT = 600
            mock_settings.NW_BANDWIDTH = 8
            mock_settings.NW_MULT = 3
            mock_settings.NW_LOOKBACK = 500

            engine.position_service.has_open_position.return_value = False
            mock_gw.get_futures_klines.return_value = [[]] * 600
            mock_klines.return_value = _make_df(600, signal_type="long")
            mock_nw.return_value = _make_df(600, signal_type="long")

            signal = await engine._evaluate_symbol("BTCUSDT")
            assert signal == "long"

    async def test_short_signal(self, engine):
        with (
            _patch_asyncio_to_thread(),
            patch("services.strategy_engine.calculate_nadaraya_watson") as mock_nw,
            patch("services.strategy_engine.klines_to_dataframe") as mock_klines,
            patch("services.strategy_engine.binance_gateway") as mock_gw,
            patch("services.strategy_engine.settings") as mock_settings,
        ):
            mock_settings.STRATEGY_TIMEFRAME = "15m"
            mock_settings.STRATEGY_KLINES_LIMIT = 600
            mock_settings.NW_BANDWIDTH = 8
            mock_settings.NW_MULT = 3
            mock_settings.NW_LOOKBACK = 500

            engine.position_service.has_open_position.return_value = False
            mock_gw.get_futures_klines.return_value = [[]] * 600
            mock_klines.return_value = _make_df(600, signal_type="short")
            mock_nw.return_value = _make_df(600, signal_type="short")

            signal = await engine._evaluate_symbol("BTCUSDT")
            assert signal == "short"

    async def test_no_signal(self, engine):
        with (
            _patch_asyncio_to_thread(),
            patch("services.strategy_engine.calculate_nadaraya_watson") as mock_nw,
            patch("services.strategy_engine.klines_to_dataframe") as mock_klines,
            patch("services.strategy_engine.binance_gateway") as mock_gw,
            patch("services.strategy_engine.settings") as mock_settings,
        ):
            mock_settings.STRATEGY_TIMEFRAME = "15m"
            mock_settings.STRATEGY_KLINES_LIMIT = 600
            mock_settings.NW_BANDWIDTH = 8
            mock_settings.NW_MULT = 3
            mock_settings.NW_LOOKBACK = 500

            engine.position_service.has_open_position.return_value = False
            mock_gw.get_futures_klines.return_value = [[]] * 600
            mock_klines.return_value = _make_df(600, signal_type=None)
            mock_nw.return_value = _make_df(600, signal_type=None)

            signal = await engine._evaluate_symbol("BTCUSDT")
            assert signal is None

    async def test_skip_when_position_open(self, engine):
        with patch("services.strategy_engine.settings"):
            engine.position_service.has_open_position.return_value = True
            signal = await engine._evaluate_symbol("BTCUSDT")
            assert signal is None

    async def test_not_enough_candles(self, engine):
        with (
            _patch_asyncio_to_thread(),
            patch("services.strategy_engine.binance_gateway") as mock_gw,
            patch("services.strategy_engine.settings") as mock_settings,
        ):
            mock_settings.NW_LOOKBACK = 500
            mock_settings.STRATEGY_TIMEFRAME = "15m"
            mock_settings.STRATEGY_KLINES_LIMIT = 600

            engine.position_service.has_open_position.return_value = False
            mock_gw.get_futures_klines.return_value = [[]] * 10

            signal = await engine._evaluate_symbol("BTCUSDT")
            assert signal is None

    async def test_invalid_symbol_returns_none(self, engine):
        from binance.exceptions import BinanceAPIException

        with (
            _patch_asyncio_to_thread(),
            patch("services.strategy_engine.binance_gateway") as mock_gw,
            patch("services.strategy_engine.settings") as mock_settings,
        ):
            mock_settings.STRATEGY_TIMEFRAME = "15m"
            mock_settings.STRATEGY_KLINES_LIMIT = 600
            mock_settings.NW_LOOKBACK = 500

            engine.position_service.has_open_position.return_value = False
            resp = MagicMock()
            resp.status_code = 400
            resp.text = '{"code":-1121,"msg":"Invalid symbol."}'
            mock_gw.get_futures_klines.side_effect = BinanceAPIException(resp, 400, resp.text)

            signal = await engine._evaluate_symbol("PEPEUSDT")
            assert signal is None


# ── _place_strategy_tp_sl ──────────────────────────────────────


class TestPlaceStrategyTpSl:
    async def test_tp_sl_prices_positive(self, engine):
        with (
            _patch_asyncio_to_thread(),
            patch("services.strategy_engine.round_price_with_precision", side_effect=lambda p, s: round(p, 4)),
            patch("services.strategy_engine.binance_gateway") as mock_gw,
            patch("services.strategy_engine.settings") as mock_settings,
        ):
            mock_settings.STRATEGY_TP_PERCENT = 30
            mock_settings.STRATEGY_SL_PERCENT = 15

            mock_gw.create_take_profit_market_order.return_value = {"orderId": "tp1"}
            mock_gw.create_stop_loss_order.return_value = {"orderId": "sl1"}

            order_info = {"order_id": "123"}
            await engine._place_strategy_tp_sl("TRXUSDT", "BUY", 1000, 0.05, 10, order_info)
            call_args = mock_gw.create_stop_loss_order.call_args
            stop_price = call_args[0][3]
            assert stop_price > 0

    async def test_sl_clamped_to_minimum(self, engine):
        with (
            _patch_asyncio_to_thread(),
            patch("services.strategy_engine.round_price_with_precision", side_effect=lambda p, s: round(p, 4)),
            patch("services.strategy_engine.binance_gateway") as mock_gw,
            patch("services.strategy_engine.settings") as mock_settings,
        ):
            mock_settings.STRATEGY_TP_PERCENT = 30
            mock_settings.STRATEGY_SL_PERCENT = 500  # very high SL%

            mock_gw.create_take_profit_market_order.return_value = {"orderId": "tp1"}
            mock_gw.create_stop_loss_order.return_value = {"orderId": "sl1"}

            order_info = {"order_id": "123"}
            await engine._place_strategy_tp_sl("TRXUSDT", "BUY", 100000, 0.0001, 10, order_info)
            call_args = mock_gw.create_stop_loss_order.call_args
            stop_price = call_args[0][3]
            assert stop_price > 0


# ── _evaluate_all_symbols ─────────────────────────────────────


class TestEvaluateAllSymbols:
    async def test_skips_when_max_positions_reached(self, engine):
        with patch("services.strategy_engine.settings") as mock_settings:
            mock_settings.MAX_CONCURRENT_POSITIONS = 2
            mock_settings.STRATEGY_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
            engine.position_store.get_open_positions.return_value = [{"id": 1}, {"id": 2}]

            await engine._evaluate_all_symbols()
            engine.position_service.has_open_position.assert_not_called()


# ── get_status ─────────────────────────────────────────────────


class TestGetStatus:
    @patch("services.strategy_engine.settings")
    def test_returns_dict(self, mock_settings, engine):
        mock_settings.STRATEGY_ENABLED = True
        mock_settings.STRATEGY_SYMBOLS = ["BTCUSDT"]
        mock_settings.STRATEGY_TIMEFRAME = "15m"
        mock_settings.STRATEGY_LEVERAGE = 5
        mock_settings.MAX_CONCURRENT_POSITIONS = 3
        mock_settings.RISK_PER_TRADE_PERCENT = 1.0
        mock_settings.NW_BANDWIDTH = 8
        mock_settings.NW_MULT = 3
        mock_settings.NW_LOOKBACK = 500
        mock_settings.STRATEGY_TP_PERCENT = 30
        mock_settings.STRATEGY_SL_PERCENT = 15

        status = engine.get_status()
        assert status["strategy"] == "nadaraya_watson"
        assert "symbols" in status
        assert "pending_signals" in status
