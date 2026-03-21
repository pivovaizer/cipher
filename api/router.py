from fastapi import APIRouter

from api.routers.health import router as health_router
from api.routers.positions import router as positions_router
from api.routers.signals import router as signals_router
from api.routers.strategy import router as strategy_router
from api.routers.trading import router as trading_router
from api.routers.webhook import router as webhook_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(webhook_router)
api_router.include_router(positions_router)
api_router.include_router(signals_router)
api_router.include_router(trading_router)
api_router.include_router(strategy_router)

