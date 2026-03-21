import logging

from fastapi import APIRouter, HTTPException

from api.schemas import WebhookRequest, WebhookResponse
from config import settings
from services.adapters import (
    add_pending_order,
    clean_symbol,
    order_manager,
    signal_manager,
    signal_tracker,
    to_legacy_order_request,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhook"])


@router.post("/webhook", response_model=WebhookResponse)
async def webhook_handler(payload: WebhookRequest) -> WebhookResponse:
    try:
        cleaned_symbol = clean_symbol(payload.ticker)
        logger.info("Received signal: %s %s %s", cleaned_symbol, payload.action.value, payload.time.isoformat())

        legacy_request = to_legacy_order_request(payload)
        should_trade = signal_manager.process_signal(legacy_request)

        if not should_trade:
            return WebhookResponse(message="Signal accepted for delayed processing")

        side = "BUY" if payload.action.value == "long" else "SELL"
        order, order_info = order_manager.place_main_order(
            symbol=payload.ticker,
            side=side,
            price=payload.price,
            investment_amount=settings.INVESTMENT_AMOUNT,
            leverage=settings.LEVERAGE,
        )

        add_pending_order(order_info)
        signal_tracker.add_processed_signal(legacy_request, order_info)

        return WebhookResponse(
            message="Order placed successfully",
            main_order=order,
            tp_sl_orders=None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Webhook processing failed")
        try:
            signal_tracker.add_rejected_signal(to_legacy_order_request(payload), f"Processing error: {exc}")
        except Exception:
            logger.exception("Failed to write rejected signal")
        raise HTTPException(status_code=500, detail="Internal server error") from exc
