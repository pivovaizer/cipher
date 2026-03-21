import logging
from datetime import datetime, timezone
from typing import Any

from binance.enums import SIDE_BUY, SIDE_SELL

from config import settings
from services.binance_gateway import BinanceGateway, binance_gateway
from services.calculations import (
    calculate_quantity,
    calculate_stop_loss_price,
    calculate_stop_loss_price_by_roi,
    calculate_take_profit_price,
    calculate_take_profit_price_by_roi,
    round_price_with_precision,
)
from services.symbols import clean_symbol

logger = logging.getLogger(__name__)


class OrderManager:
    def __init__(self, gateway: BinanceGateway = binance_gateway) -> None:
        self.gateway = gateway

    def place_main_order(
        self,
        symbol: str,
        side: str,
        price: float,
        investment_amount: float,
        leverage: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        cleaned = clean_symbol(symbol)
        if price is None:
            raise ValueError("Price is required for limit orders")
        if not self.gateway.check_account_balance(investment_amount):
            raise ValueError("Insufficient balance")

        quantity = calculate_quantity(price, investment_amount, leverage, cleaned)
        rounded_price = round_price_with_precision(price, cleaned)
        self.gateway.set_leverage(cleaned, leverage)
        order = self.gateway.create_limit_order(cleaned, side, quantity, rounded_price)
        order_info = {
            "symbol": cleaned,
            "status": "pending",
            "side": side,
            "quantity": quantity,
            "entry_price": rounded_price,
            "investment": investment_amount,
            "leverage": leverage,
            "order_id": order["orderId"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return order, order_info

    def place_market_order(
        self,
        symbol: str,
        side: str,
        investment_amount: float,
        leverage: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        cleaned = clean_symbol(symbol)
        if not self.gateway.check_account_balance(investment_amount):
            raise ValueError("Insufficient balance")

        current_price = self.gateway.get_current_price(cleaned)
        quantity = calculate_quantity(current_price, investment_amount, leverage, cleaned)
        self.gateway.set_leverage(cleaned, leverage)
        order = self.gateway.create_market_order(cleaned, side, quantity)

        tp_sl_result = None
        try:
            tp_sl_result = self.place_take_profit_and_stop_loss(
                cleaned, side, quantity, current_price, investment_amount
            )
        except Exception:
            logger.exception("Failed to place TP/SL for market order")

        order_info = {
            "symbol": cleaned,
            "status": "open",
            "side": side,
            "quantity": quantity,
            "entry_price": current_price,
            "investment": investment_amount,
            "leverage": leverage,
            "order_id": order["orderId"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "filled_at": datetime.now(timezone.utc).isoformat(),
            "tp_sl_placed": tp_sl_result is not None,
        }
        if tp_sl_result:
            order_info.update(
                {
                    "tp_order_id": tp_sl_result["take_profit"]["orderId"],
                    "sl_order_id": tp_sl_result["stop_loss"]["orderId"],
                    "tp_price": tp_sl_result["take_profit_price"],
                    "sl_price": tp_sl_result["stop_loss_price"],
                }
            )
        return order, order_info

    def place_take_profit_and_stop_loss(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        investment_amount: float,
    ) -> dict[str, Any]:
        cleaned = clean_symbol(symbol)
        if settings.USE_ROI_CALCULATION:
            tp = calculate_take_profit_price_by_roi(
                entry_price, side, quantity, investment_amount, settings.TAKE_PROFIT_ROI_PERCENT
            )
            sl = calculate_stop_loss_price_by_roi(
                entry_price, side, quantity, investment_amount, settings.STOP_LOSS_ROI_PERCENT
            )
        else:
            tp = calculate_take_profit_price(entry_price, side, settings.TAKE_PROFIT_PERCENTAGE)
            sl = calculate_stop_loss_price(entry_price, side, settings.STOP_LOSS_PERCENTAGE)

        tp = round_price_with_precision(tp, cleaned)
        sl = round_price_with_precision(sl, cleaned)
        tp_side = SIDE_SELL if side == SIDE_BUY else SIDE_BUY
        sl_side = SIDE_SELL if side == SIDE_BUY else SIDE_BUY
        tp_order = self.gateway.create_take_profit_order(cleaned, tp_side, quantity, tp)
        sl_order = self.gateway.create_stop_loss_order(cleaned, sl_side, quantity, sl)
        return {
            "take_profit": tp_order,
            "stop_loss": sl_order,
            "take_profit_price": tp,
            "stop_loss_price": sl,
        }

    def cancel_related_orders(self, symbol: str) -> list[str]:
        cleaned = clean_symbol(symbol)
        cancelled: list[str] = []
        for order in self.gateway.get_open_orders(cleaned):
            if order.get("reduceOnly"):
                try:
                    self.gateway.cancel_order(cleaned, order["orderId"])
                    cancelled.append(str(order["orderId"]))
                except Exception:
                    logger.exception("Failed to cancel order %s", order.get("orderId"))
        return cancelled


order_manager = OrderManager()
