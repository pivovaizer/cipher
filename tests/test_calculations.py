from unittest.mock import patch, MagicMock

from services.calculations import (
    calculate_take_profit_price,
    calculate_stop_loss_price,
    calculate_take_profit_price_by_roi,
    calculate_stop_loss_price_by_roi,
    calculate_quantity,
    round_price_with_precision,
)


# ── TP / SL percentage-based ──────────────────────────────────


def test_tp_buy():
    # 10% TP on BUY → price * 1.10
    assert calculate_take_profit_price(100.0, "BUY", 10.0) == pytest.approx(110.0)


def test_tp_sell():
    # 10% TP on SELL → price * 0.90
    assert calculate_take_profit_price(100.0, "SELL", 10.0) == pytest.approx(90.0)


def test_sl_buy():
    # 5% SL on BUY → price * 0.95
    assert calculate_stop_loss_price(100.0, "BUY", 5.0) == pytest.approx(95.0)


def test_sl_sell():
    # 5% SL on SELL → price * 1.05
    assert calculate_stop_loss_price(100.0, "SELL", 5.0) == pytest.approx(105.0)


# ── TP / SL ROI-based ─────────────────────────────────────────


def test_tp_by_roi_buy():
    # entry=100, qty=1, investment=10, roi=50% → profit=5 → tp=105
    result = calculate_take_profit_price_by_roi(100.0, "BUY", 1.0, 10.0, 50.0)
    assert result == pytest.approx(105.0)


def test_tp_by_roi_sell():
    # entry=100, qty=1, investment=10, roi=50% → profit=5 → tp=95
    result = calculate_take_profit_price_by_roi(100.0, "SELL", 1.0, 10.0, 50.0)
    assert result == pytest.approx(95.0)


def test_sl_by_roi_buy():
    # entry=100, qty=1, investment=10, loss=20% → max_loss=2 → sl=98
    result = calculate_stop_loss_price_by_roi(100.0, "BUY", 1.0, 10.0, 20.0)
    assert result == pytest.approx(98.0)


def test_sl_by_roi_sell():
    # entry=100, qty=1, investment=10, loss=20% → max_loss=2 → sl=102
    result = calculate_stop_loss_price_by_roi(100.0, "SELL", 1.0, 10.0, 20.0)
    assert result == pytest.approx(102.0)


# ── calculate_quantity ─────────────────────────────────────────


@patch("services.calculations.get_symbol_info")
def test_calculate_quantity(mock_info):
    mock_info.return_value = {
        "quantityPrecision": 3,
        "filters": [{"filterType": "LOT_SIZE", "minQty": "0.001"}],
    }
    # qty = (10 * 20) / 50000 = 0.004
    qty = calculate_quantity(50000.0, 10.0, 20, "BTCUSDT")
    assert qty == 0.004


@patch("services.calculations.get_symbol_info")
def test_calculate_quantity_below_min(mock_info):
    mock_info.return_value = {
        "quantityPrecision": 3,
        "filters": [{"filterType": "LOT_SIZE", "minQty": "1.0"}],
    }
    with pytest.raises(ValueError, match="below minQty"):
        calculate_quantity(50000.0, 1.0, 1, "BTCUSDT")


@patch("services.calculations.get_symbol_info")
def test_calculate_quantity_no_lot_size(mock_info):
    mock_info.return_value = {
        "quantityPrecision": 3,
        "filters": [],
    }
    with pytest.raises(ValueError, match="LOT_SIZE"):
        calculate_quantity(50000.0, 10.0, 20, "BTCUSDT")


# ── round_price_with_precision ─────────────────────────────────


@patch("services.calculations.binance_gateway")
def test_round_price_with_precision(mock_gw):
    mock_gw.get_tick_size.return_value = 0.01
    mock_gw.round_to_tick.return_value = 100.55
    result = round_price_with_precision(100.556, "BTCUSDT")
    assert result == 100.55
    mock_gw.get_tick_size.assert_called_once_with("BTCUSDT")


import pytest
