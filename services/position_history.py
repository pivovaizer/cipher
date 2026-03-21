import csv
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PositionHistoryService:
    def __init__(self, csv_file: str = "closed_positions.csv") -> None:
        self.path = Path(csv_file)
        self._lock = threading.RLock()
        self.headers = [
            "close_time",
            "symbol",
            "side",
            "entry_price",
            "exit_price",
            "quantity",
            "investment_amount",
            "profit_loss_usd",
            "profit_loss_percent",
            "close_reason",
            "duration_minutes",
            "leverage",
            "tp_price",
            "sl_price",
        ]
        self._ensure_csv_exists()

    def _ensure_csv_exists(self) -> None:
        with self._lock:
            if self.path.exists():
                return
            with self.path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(self.headers)

    def add_closed_position(self, position_data: dict[str, Any]) -> None:
        with self._lock:
            with self.path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(
                    [
                        position_data.get("close_time", datetime.now().isoformat()),
                        position_data.get("symbol", ""),
                        position_data.get("side", ""),
                        position_data.get("entry_price", 0),
                        position_data.get("exit_price", 0),
                        position_data.get("quantity", 0),
                        position_data.get("investment_amount", 0),
                        position_data.get("profit_loss_usd", 0),
                        position_data.get("profit_loss_percent", 0),
                        position_data.get("close_reason", "unknown"),
                        position_data.get("duration_minutes", 0),
                        position_data.get("leverage", 0),
                        position_data.get("tp_price", 0),
                        position_data.get("sl_price", 0),
                    ]
                )

    def _all_rows(self) -> list[dict[str, Any]]:
        with self._lock:
            if not self.path.exists():
                return []
            with self.path.open("r", encoding="utf-8") as fh:
                return list(csv.DictReader(fh))

    def get_recent_positions(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._all_rows()
        return rows[-limit:] if len(rows) > limit else rows

    def get_positions_by_symbol(self, symbol: str) -> list[dict[str, Any]]:
        return [row for row in self._all_rows() if row.get("symbol") == symbol]

    def get_trading_statistics(self) -> dict[str, Any]:
        rows = self._all_rows()
        if not rows:
            return self._empty_stats()

        total_positions = len(rows)
        total_pl = 0.0
        total_investment = 0.0
        total_duration = 0
        winning = 0
        for row in rows:
            pl = float(row.get("profit_loss_usd", 0) or 0)
            inv = float(row.get("investment_amount", 0) or 0)
            dur = int(float(row.get("duration_minutes", 0) or 0))
            total_pl += pl
            total_investment += inv
            total_duration += dur
            if pl > 0:
                winning += 1

        win_rate = (winning / total_positions) * 100 if total_positions else 0
        roi = (total_pl / total_investment) * 100 if total_investment > 0 else 0

        return {
            "total_positions": total_positions,
            "winning_positions": winning,
            "losing_positions": total_positions - winning,
            "win_rate_percent": round(win_rate, 2),
            "total_profit_loss_usd": round(total_pl, 2),
            "total_investment_usd": round(total_investment, 2),
            "total_roi_percent": round(roi, 2),
            "average_duration_minutes": round(total_duration / total_positions, 1),
            "average_profit_loss_per_trade": round(total_pl / total_positions, 2),
        }

    @staticmethod
    def _empty_stats() -> dict[str, Any]:
        return {
            "total_positions": 0,
            "winning_positions": 0,
            "losing_positions": 0,
            "win_rate_percent": 0.0,
            "total_profit_loss_usd": 0.0,
            "total_investment_usd": 0.0,
            "total_roi_percent": 0.0,
            "average_duration_minutes": 0.0,
            "average_profit_loss_per_trade": 0.0,
        }

