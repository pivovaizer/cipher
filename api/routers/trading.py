import logging
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from services.adapters import position_history

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trading", tags=["trading"])


@router.get("/statistics")
async def get_trading_statistics() -> dict:
    try:
        return position_history.get_trading_statistics()
    except Exception as exc:
        logger.exception("Failed to get trading statistics")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/history")
async def get_trading_history(limit: int = 10) -> dict:
    try:
        positions = position_history.get_recent_positions(limit)
        return {"positions": positions, "count": len(positions), "limit": limit}
    except Exception as exc:
        logger.exception("Failed to get trading history")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/history/{symbol}")
async def get_trading_history_by_symbol(symbol: str) -> dict:
    try:
        positions = position_history.get_positions_by_symbol(symbol)
        return {"symbol": symbol, "positions": positions, "count": len(positions)}
    except Exception as exc:
        logger.exception("Failed to get trading history by symbol")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/download")
async def download_trading_history() -> FileResponse:
    csv_file = "closed_positions.csv"
    try:
        if not os.path.exists(csv_file):
            raise HTTPException(status_code=404, detail="Trading history file not found")
        return FileResponse(path=csv_file, filename="trading_history.csv", media_type="text/csv")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to download trading history")
        raise HTTPException(status_code=500, detail="Internal server error") from exc
