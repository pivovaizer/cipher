import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router
from config import settings
from services.binance_gateway import binance_gateway
from services.adapters import (
    add_pending_order,
    background_task_manager,
    order_manager,
    signal_manager,
    signal_tracker,
    strategy_engine,
)

logger = logging.getLogger(__name__)


def check_futures_balance() -> None:
    try:
        futures_account = binance_gateway.client.futures_account()
        available_balance = float(futures_account["availableBalance"])
        positions = binance_gateway.get_positions()
        open_positions_count = len([p for p in positions if float(p["positionAmt"]) != 0])
        logger.info(
            "Available balance: %.2f USDT | Open positions: %d",
            available_balance,
            open_positions_count,
        )
    except Exception:
        logger.exception("Failed to check futures balance")


def open_order_callback(order_request) -> None:
    try:
        if signal_tracker.is_signal_processed(order_request):
            logger.info("Signal already processed: %s", order_request.ticker)
            return

        side = "BUY" if order_request.action.lower() == "long" else "SELL"
        if order_request.market_order:
            order, order_info = order_manager.place_market_order(
                symbol=order_request.ticker,
                side=side,
                investment_amount=settings.INVESTMENT_AMOUNT,
                leverage=settings.LEVERAGE,
            )
            logger.info("Market order opened: %s", order.get("orderId"))
            add_pending_order(order_info)
            signal_tracker.add_processed_signal(
                order_request,
                order_info,
                order_info.get("tp_price"),
                order_info.get("sl_price"),
            )
            return

        order, order_info = order_manager.place_main_order(
            symbol=order_request.ticker,
            side=side,
            price=order_request.price,
            investment_amount=settings.INVESTMENT_AMOUNT,
            leverage=settings.LEVERAGE,
        )
        logger.info("Limit order opened: %s", order.get("orderId"))
        add_pending_order(order_info)
        signal_tracker.add_processed_signal(order_request, order_info)
    except Exception as exc:
        logger.exception("Failed in order callback")
        signal_tracker.add_rejected_signal(order_request, f"Callback error: {exc}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting Cipher")
    check_futures_balance()
    signal_manager.set_order_callback(open_order_callback)
    signal_manager.start()
    await background_task_manager.start_background_tasks()
    await strategy_engine.start()
    yield
    logger.info("Stopping Cipher")
    await strategy_engine.stop()
    await background_task_manager.stop_background_tasks()
    signal_manager.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="Cipher API", version="2.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app
