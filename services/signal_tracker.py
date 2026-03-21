import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from models.order import OrderRequest

from services.storage import JsonFileStore
from services.symbols import clean_symbol

logger = logging.getLogger(__name__)


def _parse_dt(value: str) -> datetime:
    if value.endswith("Z"):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class SignalTrackerService:
    def __init__(
        self,
        processed_file: str = "processed_signals.json",
        history_file: str = "signal_history.json",
    ) -> None:
        self._processed_store = JsonFileStore(processed_file)
        self._history_store = JsonFileStore(history_file)
        self._lock = threading.RLock()
        self.processed_signals: dict[str, dict[str, Any]] = {}
        self.signal_history: list[dict[str, Any]] = []
        self.load_data()

    def _signal_id(self, order_request: OrderRequest) -> str:
        return f"{clean_symbol(order_request.ticker)}_{order_request.action.lower()}_{order_request.time}"

    def is_signal_fresh(self, order_request: OrderRequest, max_delay_minutes: int) -> bool:
        try:
            signal_time = _parse_dt(order_request.time)
            diff = datetime.now(timezone.utc) - signal_time
            return diff <= timedelta(minutes=max_delay_minutes)
        except Exception:
            logger.exception("Failed to parse signal timestamp")
            return False

    def is_signal_processed(self, order_request: OrderRequest) -> bool:
        with self._lock:
            return self._signal_id(order_request) in self.processed_signals

    def add_processed_signal(
        self,
        order_request: OrderRequest,
        order_info: dict[str, Any] | None = None,
        tp_price: float | None = None,
        sl_price: float | None = None,
    ) -> str:
        with self._lock:
            signal_id = self._signal_id(order_request)
            now_iso = datetime.now(timezone.utc).isoformat()
            payload = {
                "signal_id": signal_id,
                "ticker": clean_symbol(order_request.ticker),
                "action": order_request.action.lower(),
                "signal_time": order_request.time,
                "processed_time": now_iso,
                "price": order_request.price,
                "open": order_request.open,
                "high": order_request.high,
                "low": order_request.low,
                "market_order": order_request.market_order,
                "order_info": order_info,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "status": "processed",
            }
            self.processed_signals[signal_id] = payload
            self.signal_history.append(payload)
            self.save_data()
            return signal_id

    def add_rejected_signal(self, order_request: OrderRequest, reason: str) -> str:
        with self._lock:
            signal_id = self._signal_id(order_request)
            payload = {
                "signal_id": signal_id,
                "ticker": clean_symbol(order_request.ticker),
                "action": order_request.action.lower(),
                "signal_time": order_request.time,
                "processed_time": datetime.now(timezone.utc).isoformat(),
                "price": order_request.price,
                "open": order_request.open,
                "high": order_request.high,
                "low": order_request.low,
                "market_order": order_request.market_order,
                "order_info": None,
                "tp_price": None,
                "sl_price": None,
                "status": "rejected",
                "rejection_reason": reason,
            }
            self.signal_history.append(payload)
            self.save_data()
            return signal_id

    def get_signal_info(self, signal_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self.processed_signals.get(signal_id)

    def get_recent_signals(self, hours: int = 24) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with self._lock:
            result = []
            for signal in self.signal_history:
                try:
                    signal_time = _parse_dt(signal["signal_time"])
                    if signal_time >= cutoff:
                        result.append(signal)
                except Exception:
                    logger.exception("Failed to parse history timestamp")
            return result

    def cleanup_old_signals(self, days: int = 7) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with self._lock:
            self.processed_signals = {
                key: value
                for key, value in self.processed_signals.items()
                if _parse_dt(value["processed_time"]) >= cutoff
            }
            self.signal_history = [
                signal for signal in self.signal_history if _parse_dt(signal["processed_time"]) >= cutoff
            ]
            self.save_data()

    def get_statistics(self) -> dict[str, Any]:
        with self._lock:
            actions_count: dict[str, int] = {}
            status_count: dict[str, int] = {}
            for signal in self.signal_history:
                action = signal.get("action", "unknown")
                status = signal.get("status", "unknown")
                actions_count[action] = actions_count.get(action, 0) + 1
                status_count[status] = status_count.get(status, 0) + 1
            return {
                "total_processed": len(self.processed_signals),
                "total_history": len(self.signal_history),
                "actions_count": actions_count,
                "status_count": status_count,
                "last_update": datetime.now(timezone.utc).isoformat(),
            }

    def save_data(self) -> None:
        self._processed_store.write(
            {
                "processed_signals": self.processed_signals,
                "last_update": datetime.now(timezone.utc).isoformat(),
                "total_processed": len(self.processed_signals),
            }
        )
        self._history_store.write(
            {
                "signal_history": self.signal_history,
                "last_update": datetime.now(timezone.utc).isoformat(),
                "total_signals": len(self.signal_history),
            }
        )

    def load_data(self) -> None:
        with self._lock:
            processed = self._processed_store.read({})
            history = self._history_store.read({})
            self.processed_signals = processed.get("processed_signals", {})
            self.signal_history = history.get("signal_history", [])
