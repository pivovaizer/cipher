from dataclasses import dataclass
from typing import Optional


@dataclass
class OrderRequest:
    ticker: str
    action: str
    time: str
    price: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    market_order: bool = False
