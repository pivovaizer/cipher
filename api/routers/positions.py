import logging

from fastapi import APIRouter, HTTPException

from config import settings
from services.adapters import (
    add_manual_position,
    close_manual_position,
    get_all_positions,
    get_positions_summary,
    get_trading_summary,
    has_open_position,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("")
async def get_positions() -> dict:
    try:
        return {
            "positions": get_positions_summary(),
            "trading": get_trading_summary(),
        }
    except Exception as exc:
        logger.exception("Failed to get positions")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/all")
async def get_all_positions_endpoint() -> dict:
    try:
        return get_all_positions()
    except Exception as exc:
        logger.exception("Failed to get all positions")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/check/{symbol}")
async def check_position(symbol: str) -> dict:
    try:
        return {"symbol": symbol, "has_open_position": has_open_position(symbol)}
    except Exception as exc:
        logger.exception("Failed to check position")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/manual/add")
async def add_manual_position_endpoint(
    symbol: str,
    side: str,
    quantity: float,
    entry_price: float,
    investment_amount: float | None = None,
    leverage: int | None = None,
) -> dict:
    try:
        add_manual_position(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            investment_amount=investment_amount if investment_amount is not None else settings.INVESTMENT_AMOUNT,
            leverage=leverage if leverage is not None else settings.LEVERAGE,
        )
        return {
            "message": f"Manual position added: {symbol} {side}",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "entry_price": entry_price,
        }
    except Exception as exc:
        logger.exception("Failed to add manual position")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/manual/close")
async def close_manual_position_endpoint(
    symbol: str,
    close_price: float,
    close_reason: str = "manual_close",
) -> dict:
    try:
        close_manual_position(symbol=symbol, close_price=close_price, close_reason=close_reason)
        return {
            "message": f"Manual position closed: {symbol}",
            "symbol": symbol,
            "close_price": close_price,
            "close_reason": close_reason,
        }
    except Exception as exc:
        logger.exception("Failed to close manual position")
        raise HTTPException(status_code=500, detail="Internal server error") from exc
