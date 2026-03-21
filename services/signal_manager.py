import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

from models.order import OrderRequest

from config import settings
from services.position_service import PositionService
from services.signal_tracker import SignalTrackerService
from services.symbols import clean_symbol

logger = logging.getLogger(__name__)


class SignalManagerService:
    def __init__(
        self,
        signal_tracker: SignalTrackerService,
        position_service: PositionService,
    ) -> None:
        self.signal_tracker = signal_tracker
        self.position_service = position_service
        self.order_callback: Callable[[OrderRequest], None] | None = None
        self.wait_minutes = 5
        self._active_signals: dict[str, dict] = {}
        self._lock = threading.RLock()
        self._running = False
        self._timer_thread: threading.Thread | None = None

    def set_order_callback(self, callback: Callable[[OrderRequest], None]) -> None:
        self.order_callback = callback

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
            self._timer_thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
            thread = self._timer_thread
            self._timer_thread = None
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def process_signal(self, order_request: OrderRequest) -> bool:
        ticker = clean_symbol(order_request.ticker)
        action = order_request.action.lower()

        if not self.signal_tracker.is_signal_fresh(order_request, settings.SIGNAL_MAX_DELAY_MINUTES):
            self.signal_tracker.add_rejected_signal(order_request, "Signal is stale")
            return False

        if self.position_service.has_open_position(ticker):
            self.signal_tracker.add_rejected_signal(order_request, "Open position already exists")
            return False

        wait_until = self._next_candle_end(datetime.now(timezone.utc))
        with self._lock:
            if ticker in self._active_signals:
                state = self._active_signals[ticker]
                state["signal_count"] += 1
                state["last_signal_time"] = order_request.time
                state["last_signal_price"] = order_request.price or 0
                state["action"] = action
                state["wait_until"] = wait_until
            else:
                self._active_signals[ticker] = {
                    "ticker": ticker,
                    "signal_count": 1,
                    "last_signal_time": order_request.time,
                    "last_signal_price": order_request.price or 0,
                    "action": action,
                    "wait_until": wait_until,
                }
        return False

    def _next_candle_end(self, current: datetime) -> datetime:
        next_hour = current.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return next_hour + timedelta(minutes=self.wait_minutes)

    def _timer_loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
                now = datetime.now(timezone.utc)
                expired = [k for k, v in self._active_signals.items() if now >= v["wait_until"]]
                ready = [self._active_signals[k] for k in expired]
                for key in expired:
                    del self._active_signals[key]

            for signal_data in ready:
                self._fire_callback(signal_data)
            time.sleep(2)

    def _fire_callback(self, signal_data: dict) -> None:
        if not self.order_callback:
            return
        try:
            request = OrderRequest(
                ticker=signal_data["ticker"],
                action=signal_data["action"],
                time=signal_data["last_signal_time"],
                price=signal_data["last_signal_price"],
                market_order=True,
                open=0,
                high=0,
                low=0,
            )
            self.order_callback(request)
        except Exception:
            logger.exception("Failed to execute delayed order callback")
