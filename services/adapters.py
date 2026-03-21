from datetime import timezone

from models.order import OrderRequest

from api.schemas import WebhookRequest
from services.background_tasks import BackgroundTaskService
from services.order_manager import order_manager
from services.position_history import PositionHistoryService
from services.position_service import PositionService
from services.position_store import PositionStoreService
from services.signal_manager import SignalManagerService
from services.signal_tracker import SignalTrackerService
from services.symbols import clean_symbol

position_store = PositionStoreService()
position_service = PositionService(position_store)
position_history = PositionHistoryService()
signal_tracker = SignalTrackerService()
signal_manager = SignalManagerService(signal_tracker=signal_tracker, position_service=position_service)
background_task_manager = BackgroundTaskService(
    position_store=position_store,
    position_service=position_service,
    position_history=position_history,
    signal_tracker=signal_tracker,
)

from services.strategy_engine import StrategyEngine

strategy_engine = StrategyEngine(
    order_manager=order_manager,
    position_service=position_service,
    position_store=position_store,
)


def to_legacy_order_request(payload: WebhookRequest) -> OrderRequest:
    signal_time = payload.time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return OrderRequest(
        ticker=clean_symbol(payload.ticker),
        action=payload.action.value,
        time=signal_time,
        price=payload.price,
        open=payload.open,
        high=payload.high,
        low=payload.low,
        market_order=payload.market_order,
    )


def add_pending_order(order_info: dict) -> None:
    order_info["symbol"] = clean_symbol(order_info.get("symbol", ""))
    position_store.add_order(order_info)


def has_open_position(symbol: str) -> bool:
    return position_service.has_open_position(clean_symbol(symbol))


def add_manual_position(
    symbol: str,
    side: str,
    quantity: float,
    entry_price: float,
    investment_amount: float,
    leverage: int,
):
    return position_store.add_manual_position(
        symbol=clean_symbol(symbol),
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        investment_amount=investment_amount,
        leverage=leverage,
    )


def close_manual_position(symbol: str, close_price: float, close_reason: str = "manual_close") -> bool:
    return position_store.close_manual_position(
        symbol=clean_symbol(symbol),
        close_price=close_price,
        close_reason=close_reason,
    )


def get_positions_summary() -> dict:
    return position_service.get_positions_summary()


def get_trading_summary() -> dict:
    return position_service.get_trading_summary()


def get_all_positions() -> dict:
    return position_service.get_all_positions()


__all__ = [
    "OrderRequest",
    "add_manual_position",
    "add_pending_order",
    "background_task_manager",
    "clean_symbol",
    "close_manual_position",
    "get_all_positions",
    "get_positions_summary",
    "get_trading_summary",
    "has_open_position",
    "order_manager",
    "position_history",
    "position_store",
    "signal_manager",
    "signal_tracker",
    "strategy_engine",
    "to_legacy_order_request",
]
