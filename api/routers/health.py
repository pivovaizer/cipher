from fastapi import APIRouter

from services.adapters import background_task_manager, signal_tracker

router = APIRouter(tags=["health"])


@router.get("/")
async def root() -> dict:
    return {"message": "Cipher API", "status": "running"}


@router.get("/status")
async def get_status() -> dict:
    return {
        "status": "running",
        "summary": background_task_manager.get_status_summary(),
        "signals": signal_tracker.get_statistics(),
    }

