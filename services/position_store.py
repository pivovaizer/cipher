import logging
import threading
from datetime import datetime
from typing import Any

from services.storage import JsonFileStore

logger = logging.getLogger(__name__)


class PositionStoreService:
    def __init__(self, path: str = "positions.json") -> None:
        self._store = JsonFileStore(path)
        self._lock = threading.RLock()

    def load_positions(self) -> list[dict[str, Any]]:
        with self._lock:
            payload = self._store.read([])
            return payload if isinstance(payload, list) else []

    def save_positions(self, positions: list[dict[str, Any]]) -> None:
        with self._lock:
            self._store.write(positions)

    def add_order(self, order_info: dict[str, Any]) -> None:
        with self._lock:
            positions = self.load_positions()
            positions.append(order_info)
            self.save_positions(positions)

    def update_order_status(
        self,
        order_id: str,
        status: str,
        additional_data: dict[str, Any] | None = None,
    ) -> bool:
        with self._lock:
            positions = self.load_positions()
            updated = False
            for position in positions:
                if str(position.get("order_id")) == str(order_id):
                    position["status"] = status
                    if additional_data:
                        position.update(additional_data)
                    updated = True
                    break
            if updated:
                self.save_positions(positions)
            return updated

    def remove_by_order_id(self, order_id: str) -> bool:
        with self._lock:
            positions = self.load_positions()
            filtered = [p for p in positions if str(p.get("order_id")) != str(order_id)]
            removed = len(filtered) != len(positions)
            if removed:
                self.save_positions(filtered)
            return removed

    def remove_by_symbol(self, symbol: str) -> int:
        with self._lock:
            positions = self.load_positions()
            filtered = [p for p in positions if p.get("symbol") != symbol]
            removed_count = len(positions) - len(filtered)
            if removed_count:
                self.save_positions(filtered)
            return removed_count

    def get_pending_orders(self) -> list[dict[str, Any]]:
        with self._lock:
            return [p for p in self.load_positions() if p.get("status") == "pending"]

    def get_open_positions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [p for p in self.load_positions() if p.get("status") == "open"]

    def add_manual_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        investment_amount: float,
        leverage: int,
        order_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            position = {
                "symbol": symbol,
                "status": "open",
                "side": side,
                "quantity": quantity,
                "entry_price": entry_price,
                "investment": investment_amount,
                "leverage": leverage,
                "order_id": order_id or f"manual_{datetime.now().timestamp()}",
                "created_at": datetime.now().isoformat(),
                "manual": True,
            }
            positions = self.load_positions()
            positions.append(position)
            self.save_positions(positions)
            return position

    def close_manual_position(
        self,
        symbol: str,
        close_price: float,
        close_reason: str,
    ) -> bool:
        with self._lock:
            positions = self.load_positions()
            updated = False
            for position in positions:
                if position.get("symbol") == symbol and position.get("status") == "open":
                    position["status"] = "closed"
                    position["close_price"] = close_price
                    position["close_reason"] = close_reason
                    position["close_time"] = datetime.now().isoformat()
                    updated = True
                    break
            if updated:
                self.save_positions(positions)
            return updated

