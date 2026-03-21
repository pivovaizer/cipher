from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator


class OrderAction(str, Enum):
    LONG = "long"
    SHORT = "short"


class WebhookRequest(BaseModel):
    ticker: str
    action: OrderAction
    time: datetime
    price: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    market_order: bool = False

    @field_validator("ticker")
    @classmethod
    def ticker_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("ticker must not be empty")
        return value

    @field_validator("time")
    @classmethod
    def normalize_time_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class WebhookResponse(BaseModel):
    message: str
    main_order: Optional[dict] = None
    tp_sl_orders: Optional[dict] = None
    error: Optional[str] = None
