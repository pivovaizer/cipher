import logging

from fastapi import APIRouter, HTTPException

from services.adapters import signal_tracker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/statistics")
async def get_signals_statistics() -> dict:
    try:
        return signal_tracker.get_statistics()
    except Exception as exc:
        logger.exception("Failed to get signal statistics")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/recent")
async def get_recent_signals(hours: int = 24) -> dict:
    try:
        recent = signal_tracker.get_recent_signals(hours)
        return {"recent_signals": recent, "hours": hours, "count": len(recent)}
    except Exception as exc:
        logger.exception("Failed to get recent signals")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/check/{signal_id}")
async def check_signal(signal_id: str) -> dict:
    try:
        signal_info = signal_tracker.get_signal_info(signal_id)
        if not signal_info:
            raise HTTPException(status_code=404, detail="Signal not found")
        return signal_info
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to check signal")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/cleanup")
async def cleanup_old_signals(days: int = 7) -> dict:
    try:
        signal_tracker.cleanup_old_signals(days)
        return {"message": f"Cleaned signals older than {days} days", "days": days}
    except Exception as exc:
        logger.exception("Failed to cleanup signals")
        raise HTTPException(status_code=500, detail="Internal server error") from exc
