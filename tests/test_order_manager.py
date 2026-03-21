from unittest.mock import MagicMock, patch

import pytest

from services.order_manager import OrderManager


@pytest.fixture
def gateway():
    gw = MagicMock()
    gw.check_account_balance.return_value = True
    gw.get_current_price.return_value = 50000.0
    gw.create_limit_order.return_value = {"orderId": "limit_1"}
    gw.create_market_order.return_value = {"orderId": "market_1"}
    gw.create_take_profit_order.return_value = {"orderId": "tp_1"}
    gw.create_stop_loss_order.return_value = {"orderId": "sl_1"}
    gw.round_to_tick.side_effect = lambda p, t: round(p, 2)
    gw.get_tick_size.return_value = 0.01
    return gw


@pytest.fixture
def manager(gateway):
    return OrderManager(gateway=gateway)


class TestPlaceMainOrder:
    @patch("services.order_manager.calculate_quantity", return_value=0.004)
    @patch("services.order_manager.round_price_with_precision", side_effect=lambda p, s: p)
    def test_success(self, mock_round, mock_qty, manager, gateway):
        order, info = manager.place_main_order("BTCUSDT", "BUY", 50000.0, 10.0, 20)
        assert order["orderId"] == "limit_1"
        assert info["status"] == "pending"
        assert info["symbol"] == "BTCUSDT"
        gateway.set_leverage.assert_called_once_with("BTCUSDT", 20)

    @patch("services.order_manager.calculate_quantity", return_value=0.004)
    @patch("services.order_manager.round_price_with_precision", side_effect=lambda p, s: p)
    def test_insufficient_balance(self, mock_round, mock_qty, manager, gateway):
        gateway.check_account_balance.return_value = False
        with pytest.raises(ValueError, match="Insufficient balance"):
            manager.place_main_order("BTCUSDT", "BUY", 50000.0, 10.0, 20)

    def test_price_required(self, manager):
        with pytest.raises(ValueError, match="Price is required"):
            manager.place_main_order("BTCUSDT", "BUY", None, 10.0, 20)

    @patch("services.order_manager.calculate_quantity", return_value=0.004)
    @patch("services.order_manager.round_price_with_precision", side_effect=lambda p, s: p)
    def test_cleans_symbol(self, mock_round, mock_qty, manager, gateway):
        manager.place_main_order("BTCUSDT.P", "BUY", 50000.0, 10.0, 20)
        gateway.create_limit_order.assert_called_once()
        args = gateway.create_limit_order.call_args[0]
        assert args[0] == "BTCUSDT"  # cleaned


class TestPlaceMarketOrder:
    @patch("services.order_manager.calculate_quantity", return_value=0.004)
    @patch("services.order_manager.round_price_with_precision", side_effect=lambda p, s: p)
    @patch("services.order_manager.settings")
    def test_success(self, mock_settings, mock_round, mock_qty, manager, gateway):
        mock_settings.USE_ROI_CALCULATION = False
        mock_settings.TAKE_PROFIT_PERCENTAGE = 10.0
        mock_settings.STOP_LOSS_PERCENTAGE = 5.0
        order, info = manager.place_market_order("BTCUSDT", "BUY", 10.0, 20)
        assert order["orderId"] == "market_1"
        assert info["status"] == "open"
        assert info["tp_sl_placed"] is True

    @patch("services.order_manager.calculate_quantity", return_value=0.004)
    def test_insufficient_balance(self, mock_qty, manager, gateway):
        gateway.check_account_balance.return_value = False
        with pytest.raises(ValueError, match="Insufficient balance"):
            manager.place_market_order("BTCUSDT", "BUY", 10.0, 20)

    @patch("services.order_manager.calculate_quantity", return_value=0.004)
    @patch("services.order_manager.round_price_with_precision", side_effect=lambda p, s: p)
    @patch("services.order_manager.settings")
    def test_tp_sl_failure_doesnt_crash(self, mock_settings, mock_round, mock_qty, manager, gateway):
        mock_settings.USE_ROI_CALCULATION = False
        mock_settings.TAKE_PROFIT_PERCENTAGE = 10.0
        mock_settings.STOP_LOSS_PERCENTAGE = 5.0
        gateway.create_take_profit_order.side_effect = Exception("API error")
        order, info = manager.place_market_order("BTCUSDT", "BUY", 10.0, 20)
        assert info["tp_sl_placed"] is False


class TestCancelRelatedOrders:
    def test_cancel_reduce_only_orders(self, manager, gateway):
        gateway.get_open_orders.return_value = [
            {"orderId": "1", "reduceOnly": True},
            {"orderId": "2", "reduceOnly": False},
            {"orderId": "3", "reduceOnly": True},
        ]
        cancelled = manager.cancel_related_orders("BTCUSDT")
        assert len(cancelled) == 2
        assert "1" in cancelled
        assert "3" in cancelled

    def test_cancel_handles_errors(self, manager, gateway):
        gateway.get_open_orders.return_value = [
            {"orderId": "1", "reduceOnly": True},
        ]
        gateway.cancel_order.side_effect = Exception("timeout")
        cancelled = manager.cancel_related_orders("BTCUSDT")
        assert len(cancelled) == 0
