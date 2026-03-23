import os
from dotenv import load_dotenv

load_dotenv()


def _to_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    def __init__(self) -> None:
        self.BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
        self.BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

        self.INVESTMENT_AMOUNT = float(os.getenv("INVESTMENT_AMOUNT", "5"))
        self.LEVERAGE = int(os.getenv("LEVERAGE", "20"))

        self.USE_ROI_CALCULATION = _to_bool(os.getenv("USE_ROI_CALCULATION"), True)
        self.TAKE_PROFIT_ROI_PERCENT = float(os.getenv("TAKE_PROFIT_ROI_PERCENT", "50.0"))
        self.STOP_LOSS_ROI_PERCENT = float(os.getenv("STOP_LOSS_ROI_PERCENT", "20.0"))
        self.TAKE_PROFIT_PERCENTAGE = float(os.getenv("TAKE_PROFIT_PERCENTAGE", "10.0"))
        self.STOP_LOSS_PERCENTAGE = float(os.getenv("STOP_LOSS_PERCENTAGE", "20.0"))

        self.PENDING_ORDERS_CHECK_INTERVAL = int(os.getenv("PENDING_ORDERS_CHECK_INTERVAL", "30"))
        self.OPEN_POSITIONS_CHECK_INTERVAL = int(os.getenv("OPEN_POSITIONS_CHECK_INTERVAL", "300"))
        self.SIGNAL_MAX_DELAY_MINUTES = int(os.getenv("SIGNAL_MAX_DELAY_MINUTES", "5"))

        self.HOST = os.getenv("HOST", "127.0.0.1")
        self.PORT = int(os.getenv("PORT", "8000"))
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

        # Strategy Engine
        self.STRATEGY_ENABLED = _to_bool(os.getenv("STRATEGY_ENABLED"), False)
        self.STRATEGY_SYMBOLS = [
            s.strip() for s in os.getenv("STRATEGY_SYMBOLS", "BTCUSDT,ETHUSDT").split(",") if s.strip()
        ]
        self.STRATEGY_TIMEFRAME = os.getenv("STRATEGY_TIMEFRAME", "15m")
        self.STRATEGY_KLINES_LIMIT = int(os.getenv("STRATEGY_KLINES_LIMIT", "1050"))

        # Nadaraya-Watson indicator parameters
        self.NW_BANDWIDTH = float(os.getenv("NW_BANDWIDTH", "8"))
        self.NW_MULT = float(os.getenv("NW_MULT", "3"))
        self.NW_LOOKBACK = int(os.getenv("NW_LOOKBACK", "500"))

        # Strategy TP/SL (percentage of investment)
        self.STRATEGY_TP_PERCENT = float(os.getenv("STRATEGY_TP_PERCENT", "30"))
        self.STRATEGY_SL_PERCENT = float(os.getenv("STRATEGY_SL_PERCENT", "15"))

        # Strategy risk management
        self.STRATEGY_LEVERAGE = int(os.getenv("STRATEGY_LEVERAGE", "5"))
        self.STRATEGY_USE_FIXED_AMOUNT = _to_bool(os.getenv("STRATEGY_USE_FIXED_AMOUNT"), True)
        self.STRATEGY_FIXED_AMOUNT = float(os.getenv("STRATEGY_FIXED_AMOUNT", "5"))
        self.RISK_PER_TRADE_PERCENT = float(os.getenv("RISK_PER_TRADE_PERCENT", "1.0"))
        self.MAX_CONCURRENT_POSITIONS = int(os.getenv("MAX_CONCURRENT_POSITIONS", "3"))
        self.MAX_CONFIRMATION_CANDLES = int(os.getenv("MAX_CONFIRMATION_CANDLES", "2"))

        self._validate()

    def _validate(self) -> None:
        if self.INVESTMENT_AMOUNT <= 0:
            raise ValueError("INVESTMENT_AMOUNT must be > 0")
        if not (1 <= self.LEVERAGE <= 125):
            raise ValueError("LEVERAGE must be in [1, 125]")
        if self.SIGNAL_MAX_DELAY_MINUTES <= 0:
            raise ValueError("SIGNAL_MAX_DELAY_MINUTES must be > 0")
        if self.PENDING_ORDERS_CHECK_INTERVAL <= 0:
            raise ValueError("PENDING_ORDERS_CHECK_INTERVAL must be > 0")
        if self.OPEN_POSITIONS_CHECK_INTERVAL <= 0:
            raise ValueError("OPEN_POSITIONS_CHECK_INTERVAL must be > 0")
        if self.STRATEGY_ENABLED:
            if not self.STRATEGY_SYMBOLS:
                raise ValueError("STRATEGY_SYMBOLS must not be empty when strategy is enabled")
            valid_tf = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h")
            if self.STRATEGY_TIMEFRAME not in valid_tf:
                raise ValueError(f"STRATEGY_TIMEFRAME must be one of {valid_tf}")
            if not (1 <= self.STRATEGY_LEVERAGE <= 50):
                raise ValueError("STRATEGY_LEVERAGE must be in [1, 50]")
            if not (0.5 <= self.RISK_PER_TRADE_PERCENT <= 5.0):
                raise ValueError("RISK_PER_TRADE_PERCENT must be in [0.5, 5.0]")
            if self.MAX_CONCURRENT_POSITIONS < 1:
                raise ValueError("MAX_CONCURRENT_POSITIONS must be >= 1")


settings = Settings()
