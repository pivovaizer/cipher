import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from config import settings
from services.binance_gateway import binance_gateway
from services.order_manager import order_manager
from services.position_history import PositionHistoryService
from services.position_service import PositionService
from services.position_store import PositionStoreService
from services.signal_tracker import SignalTrackerService

logger = logging.getLogger(__name__)


class BackgroundTaskService:
    def __init__(
        self,
        position_store: PositionStoreService,
        position_service: PositionService,
        position_history: PositionHistoryService,
        signal_tracker: SignalTrackerService,
    ) -> None:
        self.position_store = position_store
        self.position_service = position_service
        self.position_history = position_history
        self.signal_tracker = signal_tracker
        self.running = False
        self.task: asyncio.Task | None = None
        self.last_pending_check = 0.0
        self.last_position_check = 0.0
        self.last_cleanup_check = 0.0
        self.pending_interval = settings.PENDING_ORDERS_CHECK_INTERVAL
        self.open_interval = settings.OPEN_POSITIONS_CHECK_INTERVAL
        self.cleanup_interval = 24 * 60 * 60

    async def start_background_tasks(self) -> None:
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._loop())

    async def stop_background_tasks(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _loop(self) -> None:
        while self.running:
            try:
                current = time.time()
                if current - self.last_pending_check >= self.pending_interval:
                    await self._check_pending_orders()
                    self.last_pending_check = current
                if current - self.last_position_check >= self.open_interval:
                    await self._check_open_positions()
                    self.last_position_check = current
                if current - self.last_cleanup_check >= self.cleanup_interval:
                    self.signal_tracker.cleanup_old_signals(days=7)
                    self.last_cleanup_check = current
                await asyncio.sleep(3)
            except Exception:
                logger.exception("Background loop error")
                await asyncio.sleep(10)

    async def _check_pending_orders(self) -> None:
        pending = self.position_store.get_pending_orders()
        for position in pending:
            symbol = position.get("symbol")
            order_id = position.get("order_id")
            if not symbol or not order_id:
                continue
            try:
                order_status = binance_gateway.get_order_status(symbol, order_id)
                status = order_status.get("status")
                if status == "FILLED":
                    await self._handle_filled_order(position)
                elif status in {"CANCELED", "REJECTED", "EXPIRED"}:
                    self.position_store.remove_by_order_id(order_id)
            except Exception:
                logger.exception("Failed to check pending order %s", order_id)

    async def _handle_filled_order(self, position: dict[str, Any]) -> None:
        symbol = position["symbol"]
        order_id = position["order_id"]
        try:
            investment = float(position.get("investment", settings.INVESTMENT_AMOUNT))
            result = order_manager.place_take_profit_and_stop_loss(
                symbol=symbol,
                side=position["side"],
                quantity=position["quantity"],
                entry_price=position["entry_price"],
                investment_amount=investment,
            )
            self.position_store.update_order_status(
                order_id=order_id,
                status="open",
                additional_data={
                    "filled_at": datetime.now(timezone.utc).isoformat(),
                    "tp_sl_placed": True,
                    "tp_order_id": result["take_profit"]["orderId"],
                    "sl_order_id": result["stop_loss"]["orderId"],
                    "tp_price": result["take_profit_price"],
                    "sl_price": result["stop_loss_price"],
                },
            )
        except Exception as exc:
            logger.exception("Failed to place TP/SL for order %s", order_id)
            self.position_store.update_order_status(
                order_id=order_id,
                status="open",
                additional_data={"filled_at": datetime.now(timezone.utc).isoformat(), "tp_sl_error": str(exc)},
            )

    async def _check_open_positions(self) -> None:
        open_positions = self.position_store.get_open_positions()
        if not open_positions:
            return
        api_positions = self.position_service.get_current_positions_from_api()
        api_symbols = {p["symbol"] for p in api_positions}
        for position in open_positions:
            symbol = position.get("symbol")
            order_id = position.get("order_id")
            if not symbol or symbol in api_symbols:
                continue
            self.position_history.add_closed_position(self._close_payload(position))
            try:
                order_manager.cancel_related_orders(symbol)
            except Exception:
                logger.exception("Failed to cancel related orders for %s", symbol)
            if order_id:
                self.position_store.remove_by_order_id(order_id)
            else:
                self.position_store.remove_by_symbol(symbol)

    def _close_payload(self, position: dict[str, Any]) -> dict[str, Any]:
        try:
            current_price = binance_gateway.get_current_price(position["symbol"])
            entry_price = float(position.get("entry_price", 0))
            quantity = float(position.get("quantity", 0))
            investment = float(position.get("investment", settings.INVESTMENT_AMOUNT))
            side = position.get("side", "BUY")
            pl = (current_price - entry_price) * quantity if side == "BUY" else (entry_price - current_price) * quantity
            pl_pct = (pl / investment) * 100 if investment > 0 else 0
            created_at = datetime.fromisoformat(
                position.get("created_at", datetime.now(timezone.utc).isoformat())
            )
            duration = int((datetime.now(timezone.utc) - created_at).total_seconds() / 60)
            return {
                "close_time": datetime.now(timezone.utc).isoformat(),
                "symbol": position["symbol"],
                "side": side,
                "entry_price": entry_price,
                "exit_price": current_price,
                "quantity": quantity,
                "investment_amount": investment,
                "profit_loss_usd": round(pl, 2),
                "profit_loss_percent": round(pl_pct, 2),
                "close_reason": self._determine_close_reason(position),
                "duration_minutes": duration,
                "leverage": int(position.get("leverage", settings.LEVERAGE)),
                "tp_price": position.get("tp_price", 0),
                "sl_price": position.get("sl_price", 0),
            }
        except Exception:
            logger.exception("Failed to build close payload")
            return {
                "close_time": datetime.now(timezone.utc).isoformat(),
                "symbol": position.get("symbol", ""),
                "side": position.get("side", ""),
                "entry_price": 0,
                "exit_price": 0,
                "quantity": 0,
                "investment_amount": 0,
                "profit_loss_usd": 0,
                "profit_loss_percent": 0,
                "close_reason": "unknown",
                "duration_minutes": 0,
                "leverage": 0,
                "tp_price": 0,
                "sl_price": 0,
            }

    def _determine_close_reason(self, position: dict[str, Any]) -> str:
        symbol = position.get("symbol")
        tp_order_id = position.get("tp_order_id")
        sl_order_id = position.get("sl_order_id")
        if not symbol:
            return "unknown"
        if tp_order_id:
            try:
                if binance_gateway.get_order_status(symbol, tp_order_id).get("status") == "FILLED":
                    return "take_profit"
            except Exception:
                pass
        if sl_order_id:
            try:
                if binance_gateway.get_order_status(symbol, sl_order_id).get("status") == "FILLED":
                    return "stop_loss"
            except Exception:
                pass
        return "manual"

    def get_status_summary(self) -> dict[str, Any]:
        return {
            "background_tasks_running": self.running,
            "positions": self.position_service.get_positions_summary(),
            "trading": self.position_service.get_trading_summary(),
            "check_intervals": {
                "pending_orders": f"{self.pending_interval}s",
                "open_positions": f"{self.open_interval}s",
            },
        }
