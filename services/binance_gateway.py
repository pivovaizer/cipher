import logging
from typing import Any

from binance.client import Client

from config import settings

logger = logging.getLogger(__name__)


class BinanceGateway:
    def __init__(self) -> None:
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = Client(settings.BINANCE_API_KEY, settings.BINANCE_API_SECRET)
        return self._client

    def check_account_balance(self, required_amount: float) -> bool:
        try:
            info = self.client.futures_account()
            usdt = next(x for x in info["assets"] if x["asset"] == "USDT")
            return float(usdt["availableBalance"]) >= required_amount
        except Exception:
            logger.exception("Failed to check account balance")
            return False

    def get_current_price(self, symbol: str) -> float:
        ticker = self.client.futures_symbol_ticker(symbol=symbol)
        return float(ticker["price"])

    def set_leverage(self, symbol: str, leverage: int) -> None:
        self.client.futures_change_leverage(symbol=symbol, leverage=leverage)

    def create_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> dict[str, Any]:
        return self.client.futures_create_order(
            symbol=symbol,
            side=side,
            type="LIMIT",
            quantity=quantity,
            price=price,
            timeInForce="GTC",
        )

    def create_market_order(self, symbol: str, side: str, quantity: float) -> dict[str, Any]:
        return self.client.futures_create_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity,
        )

    def create_take_profit_order(self, symbol: str, side: str, quantity: float, price: float) -> dict[str, Any]:
        return self.client.futures_create_order(
            symbol=symbol,
            side=side,
            type="LIMIT",
            quantity=quantity,
            price=price,
            timeInForce="GTC",
            reduceOnly=True,
        )

    def create_take_profit_market_order(self, symbol: str, side: str, quantity: float, stop_price: float) -> dict[str, Any]:
        return self.client.futures_create_algo_order(
            symbol=symbol,
            side=side,
            type="TAKE_PROFIT_MARKET",
            triggerPrice=str(stop_price),
            quantity=str(quantity),
            reduceOnly="true",
        )

    def create_stop_loss_order(self, symbol: str, side: str, quantity: float, stop_price: float) -> dict[str, Any]:
        return self.client.futures_create_algo_order(
            symbol=symbol,
            side=side,
            type="STOP_MARKET",
            triggerPrice=str(stop_price),
            quantity=str(quantity),
            reduceOnly="true",
        )

    def get_order_status(self, symbol: str, order_id: str) -> dict[str, Any]:
        return self.client.futures_get_order(symbol=symbol, orderId=order_id)

    def cancel_order(self, symbol: str, order_id: str) -> dict[str, Any]:
        return self.client.futures_cancel_order(symbol=symbol, orderId=order_id)

    def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        if symbol:
            return self.client.futures_get_open_orders(symbol=symbol)
        return self.client.futures_get_open_orders()

    def get_positions(self) -> list[dict[str, Any]]:
        return self.client.futures_position_information()

    def get_futures_klines(self, symbol: str, interval: str, limit: int = 100) -> list[list]:
        return self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)

    def get_account_info(self) -> dict[str, Any]:
        return self.client.futures_account()

    def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        exchange_info = self.client.futures_exchange_info()
        info = next((x for x in exchange_info["symbols"] if x["symbol"] == symbol), None)
        if not info:
            raise ValueError(f"Symbol not found: {symbol}")
        return info

    def get_tick_size(self, symbol: str) -> float:
        info = self.get_symbol_info(symbol)
        price_filter = next((f for f in info["filters"] if f["filterType"] == "PRICE_FILTER"), None)
        if not price_filter:
            raise ValueError(f"PRICE_FILTER not found for {symbol}")
        return float(price_filter["tickSize"])

    def round_to_tick(self, price: float, tick_size: float) -> float:
        tick_str = str(tick_size)
        if "." in tick_str:
            precision = len(tick_str.split(".")[1].rstrip("0"))
        else:
            precision = 0
        rounded = round(price / tick_size) * tick_size
        return round(rounded, precision)


binance_gateway = BinanceGateway()
