import logging
from typing import Any

from services.binance_gateway import binance_gateway
from services.position_store import PositionStoreService

logger = logging.getLogger(__name__)


class PositionService:
    def __init__(self, store: PositionStoreService) -> None:
        self.store = store

    @staticmethod
    def get_current_positions_from_api() -> list[dict[str, Any]]:
        try:
            positions = binance_gateway.get_positions()
            return [p for p in positions if float(p["positionAmt"]) != 0]
        except Exception:
            logger.exception("Failed to fetch positions from exchange API")
            return []

    def has_open_position(self, symbol: str) -> bool:
        for position in self.store.get_open_positions():
            if position.get("symbol") == symbol:
                return True
        for position in self.get_current_positions_from_api():
            if position.get("symbol") == symbol and float(position.get("positionAmt", 0)) != 0:
                return True
        return False

    def get_positions_summary(self) -> dict[str, Any]:
        positions = self.store.load_positions()
        pending_orders = len([p for p in positions if p.get("status") == "pending"])
        open_positions = len([p for p in positions if p.get("status") == "open"])
        return {"pending_orders": pending_orders, "open_positions": open_positions, "total": len(positions)}

    def get_trading_summary(self) -> dict[str, Any]:
        positions = self.get_current_positions_from_api()
        total_pnl = 0.0
        for position in positions:
            total_pnl += float(position.get("unRealizedProfit", 0))
        return {
            "open_positions_count": len(positions),
            "total_trades": len(positions),
            "total_pnl": round(total_pnl, 2),
        }

    def get_all_positions(self) -> dict[str, Any]:
        local_positions = self.store.load_positions()
        api_positions = self.get_current_positions_from_api()
        return {
            "local_positions": local_positions,
            "api_positions": api_positions,
            "total_local": len(local_positions),
            "total_api": len(api_positions),
        }
