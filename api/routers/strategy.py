from fastapi import APIRouter

from services.adapters import strategy_engine

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get("/status")
async def strategy_status() -> dict:
    return strategy_engine.get_status()
