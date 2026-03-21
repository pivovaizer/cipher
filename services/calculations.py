from config import settings
from services.binance_gateway import binance_gateway
from services.symbols import clean_symbol


def get_symbol_info(symbol: str) -> dict:
    return binance_gateway.get_symbol_info(clean_symbol(symbol))


def round_price_with_precision(price: float, symbol: str) -> float:
    tick_size = binance_gateway.get_tick_size(symbol)
    return binance_gateway.round_to_tick(price, tick_size)


def calculate_quantity(price: float, investment_amount: float, leverage: int, symbol: str) -> float:
    info = get_symbol_info(symbol)
    qty_precision = int(info["quantityPrecision"])
    lot = next((f for f in info["filters"] if f["filterType"] == "LOT_SIZE"), None)
    if not lot:
        raise ValueError(f"LOT_SIZE filter not found for {symbol}")
    min_qty = float(lot["minQty"])
    quantity = round((investment_amount * leverage) / price, qty_precision)
    if quantity < min_qty:
        raise ValueError(f"Calculated quantity {quantity} is below minQty {min_qty}")
    return quantity


def calculate_take_profit_price(entry_price: float, side: str, percentage: float | None = None) -> float:
    percentage = settings.TAKE_PROFIT_PERCENTAGE if percentage is None else percentage
    if side == "BUY":
        return entry_price * (1 + percentage / 100)
    return entry_price * (1 - percentage / 100)


def calculate_stop_loss_price(entry_price: float, side: str, percentage: float | None = None) -> float:
    percentage = settings.STOP_LOSS_PERCENTAGE if percentage is None else percentage
    if side == "BUY":
        return entry_price * (1 - percentage / 100)
    return entry_price * (1 + percentage / 100)


def calculate_take_profit_price_by_roi(
    entry_price: float,
    side: str,
    quantity: float,
    investment_amount: float,
    roi_percent: float,
) -> float:
    desired_profit = investment_amount * (roi_percent / 100)
    if side == "BUY":
        return entry_price + (desired_profit / quantity)
    return entry_price - (desired_profit / quantity)


def calculate_stop_loss_price_by_roi(
    entry_price: float,
    side: str,
    quantity: float,
    investment_amount: float,
    loss_percent: float,
) -> float:
    max_loss = investment_amount * (loss_percent / 100)
    if side == "BUY":
        return entry_price - (max_loss / quantity)
    return entry_price + (max_loss / quantity)

