import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from binance.enums import SIDE_BUY, SIDE_SELL

from config import settings
from services.binance_gateway import binance_gateway
from services.calculations import calculate_quantity, round_price_with_precision
from services.indicators import calculate_nadaraya_watson, klines_to_dataframe
from services.order_manager import OrderManager
from services.position_service import PositionService
from services.position_store import PositionStoreService
from services.symbols import clean_symbol

logger = logging.getLogger(__name__)


class StrategyEngine:
    def __init__(
        self,
        order_manager: OrderManager,
        position_service: PositionService,
        position_store: PositionStoreService,
    ) -> None:
        self.order_manager = order_manager
        self.position_service = position_service
        self.position_store = position_store
        self._running = False
        self._task: asyncio.Task | None = None
        self.last_signals: dict[str, dict] = {}
        self.last_evaluation: str | None = None
        # Pending signals: wait for last signal in a series before executing
        # {symbol: {"signal": "long"/"short", "close": price, "count": N}}
        self._pending_signals: dict[str, dict] = {}

    async def start(self) -> None:
        if not settings.STRATEGY_ENABLED:
            logger.info("Strategy engine disabled")
            return
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "Strategy engine started: symbols=%s, timeframe=%s, leverage=%dx",
            settings.STRATEGY_SYMBOLS,
            settings.STRATEGY_TIMEFRAME,
            settings.STRATEGY_LEVERAGE,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Strategy engine stopped")

    # ── Main loop ────────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            try:
                sleep_sec = self._seconds_until_next_candle()
                logger.info("Strategy engine: sleeping %d seconds until next candle close", sleep_sec)
                await asyncio.sleep(sleep_sec + 5)  # +5s buffer for candle to finalize
                await self._evaluate_all_symbols()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Strategy engine loop error")
                await asyncio.sleep(30)

    def _seconds_until_next_candle(self) -> int:
        now = datetime.now(timezone.utc)
        tf = settings.STRATEGY_TIMEFRAME
        if tf.endswith("m"):
            interval_minutes = int(tf[:-1])
        elif tf.endswith("h"):
            interval_minutes = int(tf[:-1]) * 60
        else:
            interval_minutes = 15

        minutes_since_midnight = now.hour * 60 + now.minute
        next_boundary = ((minutes_since_midnight // interval_minutes) + 1) * interval_minutes
        target = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=next_boundary)
        diff = (target - now).total_seconds()
        return max(int(diff), 1)

    # ── Evaluation ───────────────────────────────────────────────

    async def _evaluate_all_symbols(self) -> None:
        self.last_evaluation = datetime.now(timezone.utc).isoformat()
        open_count = len(self.position_store.get_open_positions())

        if open_count >= settings.MAX_CONCURRENT_POSITIONS:
            logger.info(
                "Max concurrent positions (%d) reached, skipping", settings.MAX_CONCURRENT_POSITIONS
            )
            return

        for symbol in settings.STRATEGY_SYMBOLS:
            if open_count >= settings.MAX_CONCURRENT_POSITIONS:
                break
            try:
                cleaned = clean_symbol(symbol)
                signal = await self._evaluate_symbol(symbol)
                pending = self._pending_signals.get(cleaned)

                if signal:
                    if pending and pending["signal"] == signal:
                        # Same signal again — increment wait counter
                        pending["count"] += 1
                        pending["close"] = self.last_signals[cleaned]["close"]

                        # Force entry if max confirmation candles reached
                        if pending["count"] >= settings.MAX_CONFIRMATION_CANDLES:
                            logger.info(
                                "Max confirmation (%d) reached for %s %s, force entering",
                                pending["count"], pending["signal"], cleaned,
                            )
                            await self._execute_signal(symbol, pending["signal"])
                            open_count += 1
                            del self._pending_signals[cleaned]
                        else:
                            logger.info(
                                "Signal %s for %s repeated (%dx), waiting for confirmation",
                                signal, cleaned, pending["count"],
                            )
                    else:
                        # New signal (or different direction) — start tracking
                        self._pending_signals[cleaned] = {
                            "signal": signal,
                            "close": self.last_signals[cleaned]["close"],
                            "count": 1,
                        }
                        logger.info(
                            "Signal %s for %s detected, waiting for confirmation next candle",
                            signal, cleaned,
                        )
                else:
                    # No signal — if we had a pending one, NOW we execute it
                    if pending:
                        logger.info(
                            "Confirmed %s for %s after %d signals, executing at market",
                            pending["signal"], cleaned, pending["count"],
                        )
                        await self._execute_signal(symbol, pending["signal"])
                        open_count += 1
                        del self._pending_signals[cleaned]

            except Exception:
                logger.exception("Failed to evaluate/execute %s", symbol)

    async def _evaluate_symbol(self, symbol: str) -> str | None:
        cleaned = clean_symbol(symbol)

        if self.position_service.has_open_position(cleaned):
            logger.debug("Position already open for %s, skipping", cleaned)
            self.last_signals[cleaned] = {
                "time": datetime.now(timezone.utc).isoformat(),
                "signal": None,
                "reason": "position_already_open",
            }
            return None

        try:
            klines = await asyncio.to_thread(
                binance_gateway.get_futures_klines,
                cleaned,
                settings.STRATEGY_TIMEFRAME,
                settings.STRATEGY_KLINES_LIMIT,
            )
        except Exception as e:
            if "-1121" in str(e):
                logger.error("Invalid symbol %s — check STRATEGY_SYMBOLS config (e.g. PEPE → 1000PEPEUSDT)", cleaned)
                return None
            raise

        min_candles = settings.NW_LOOKBACK + 5
        if len(klines) < min_candles:
            logger.warning("Not enough candles for %s: got %d, need %d", cleaned, len(klines), min_candles)
            return None

        df = klines_to_dataframe(klines)
        df = calculate_nadaraya_watson(
            df,
            bandwidth=settings.NW_BANDWIDTH,
            mult=settings.NW_MULT,
            lookback=settings.NW_LOOKBACK,
        )

        # Last completed candle (iloc[-2] because iloc[-1] is the current forming candle)
        last = df.iloc[-2]

        if any(pd.isna(last[col]) for col in ("nw_lower", "nw_upper", "nw_line")):
            logger.warning("NaN indicators for %s, skipping", cleaned)
            return None

        signal = None

        # LONG: candle touches or closes below lower band
        # (same logic as Pine Script: high >= lower and low <= lower, or close < lower)
        if (last["high"] >= last["nw_lower"] and last["low"] <= last["nw_lower"]) or last["close"] < last["nw_lower"]:
            signal = "long"

        # SHORT: candle touches or closes above upper band
        elif (last["high"] >= last["nw_upper"] and last["low"] <= last["nw_upper"]) or last["close"] > last["nw_upper"]:
            signal = "short"

        self.last_signals[cleaned] = {
            "time": datetime.now(timezone.utc).isoformat(),
            "signal": signal,
            "close": float(last["close"]),
            "high": float(last["high"]),
            "low": float(last["low"]),
            "nw_line": round(float(last["nw_line"]), 4),
            "nw_upper": round(float(last["nw_upper"]), 4),
            "nw_lower": round(float(last["nw_lower"]), 4),
        }

        if signal:
            logger.info(
                "Signal for %s: %s | close=%.4f nw_lower=%.4f nw_upper=%.4f",
                cleaned, signal, last["close"], last["nw_lower"], last["nw_upper"],
            )
        else:
            logger.debug("No signal for %s", cleaned)

        return signal

    # ── Execution ────────────────────────────────────────────────

    async def _execute_signal(self, symbol: str, signal: str) -> None:
        cleaned = clean_symbol(symbol)
        side = SIDE_BUY if signal == "long" else SIDE_SELL

        investment = await self._calculate_investment()
        logger.info("Executing %s %s: investment=%.2f, leverage=%dx", signal, cleaned, investment, settings.STRATEGY_LEVERAGE)

        # Place market order without auto TP/SL (we set our own)
        current_price = await asyncio.to_thread(binance_gateway.get_current_price, cleaned)
        quantity = calculate_quantity(current_price, investment, settings.STRATEGY_LEVERAGE, cleaned)

        await asyncio.to_thread(binance_gateway.set_leverage, cleaned, settings.STRATEGY_LEVERAGE)
        order = await asyncio.to_thread(binance_gateway.create_market_order, cleaned, side, quantity)

        order_info = {
            "symbol": cleaned,
            "status": "open",
            "side": side,
            "quantity": quantity,
            "entry_price": current_price,
            "investment": investment,
            "leverage": settings.STRATEGY_LEVERAGE,
            "order_id": order["orderId"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "filled_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info("Order placed: %s %s, order_id=%s", signal, cleaned, order.get("orderId"))

        # Add to position store for background task monitoring
        self.position_store.add_order(order_info)

        # Place percentage-based TP/SL with market orders
        await self._place_strategy_tp_sl(cleaned, side, quantity, current_price, investment, order_info)

    async def _calculate_investment(self) -> float:
        if settings.STRATEGY_USE_FIXED_AMOUNT:
            logger.info("Using fixed amount: %.2f USDT", settings.STRATEGY_FIXED_AMOUNT)
            return settings.STRATEGY_FIXED_AMOUNT

        try:
            account = await asyncio.to_thread(binance_gateway.get_account_info)
            balance = float(account["availableBalance"])
            investment = balance * (settings.RISK_PER_TRADE_PERCENT / 100)
            investment = max(investment, settings.STRATEGY_FIXED_AMOUNT)
            logger.info("Using %.1f%% of balance: %.2f USDT (balance: %.2f)", settings.RISK_PER_TRADE_PERCENT, investment, balance)
            return investment
        except Exception:
            logger.warning("Failed to get balance, falling back to fixed amount: %.2f USDT", settings.STRATEGY_FIXED_AMOUNT)
            return settings.STRATEGY_FIXED_AMOUNT

    async def _place_strategy_tp_sl(
        self, symbol: str, side: str, quantity: float,
        entry_price: float, investment: float, order_info: dict,
    ) -> None:
        try:
            # Calculate TP/SL prices based on percentage of investment
            # TP% and SL% are ROI percentages: e.g. 30% TP means 30% profit on investment
            # Price move = (investment * percent / 100) / (quantity)
            tp_offset = (investment * settings.STRATEGY_TP_PERCENT / 100) / quantity
            sl_offset = (investment * settings.STRATEGY_SL_PERCENT / 100) / quantity

            if side == SIDE_BUY:
                tp_price = entry_price + tp_offset
                sl_price = entry_price - sl_offset
            else:
                tp_price = entry_price - tp_offset
                sl_price = entry_price + sl_offset

            # Ensure prices are positive (can go negative on cheap coins with high SL%)
            tp_price = max(tp_price, 0.0001)
            sl_price = max(sl_price, 0.0001)

            tp_price = round_price_with_precision(tp_price, symbol)
            sl_price = round_price_with_precision(sl_price, symbol)

            close_side = SIDE_SELL if side == SIDE_BUY else SIDE_BUY

            tp_order = await asyncio.to_thread(
                binance_gateway.create_take_profit_market_order,
                symbol, close_side, quantity, tp_price,
            )
            sl_order = await asyncio.to_thread(
                binance_gateway.create_stop_loss_order,
                symbol, close_side, quantity, sl_price,
            )

            # Update position store
            self.position_store.update_order_status(
                order_info["order_id"],
                "open",
                {
                    "tp_order_id": tp_order.get("orderId") or tp_order.get("algoId"),
                    "sl_order_id": sl_order.get("orderId") or sl_order.get("algoId"),
                    "tp_price": tp_price,
                    "sl_price": sl_price,
                    "tp_sl_placed": True,
                    "strategy": "nadaraya_watson",
                },
            )

            logger.info(
                "TP/SL for %s: TP=%.4f (+%.1f%%), SL=%.4f (-%.1f%%) | entry=%.4f",
                symbol, tp_price, settings.STRATEGY_TP_PERCENT,
                sl_price, settings.STRATEGY_SL_PERCENT, entry_price,
            )
        except Exception:
            logger.exception("Failed to place TP/SL for %s — position is UNPROTECTED", symbol)

    # ── Monitoring ───────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        return {
            "enabled": settings.STRATEGY_ENABLED,
            "running": self._running,
            "symbols": settings.STRATEGY_SYMBOLS,
            "timeframe": settings.STRATEGY_TIMEFRAME,
            "leverage": settings.STRATEGY_LEVERAGE,
            "max_positions": settings.MAX_CONCURRENT_POSITIONS,
            "risk_per_trade_percent": settings.RISK_PER_TRADE_PERCENT,
            "last_evaluation": self.last_evaluation,
            "last_signals": self.last_signals,
            "strategy": "nadaraya_watson",
            "indicators": {
                "nw_bandwidth": settings.NW_BANDWIDTH,
                "nw_mult": settings.NW_MULT,
                "nw_lookback": settings.NW_LOOKBACK,
            },
            "tp_sl": {
                "tp_percent": settings.STRATEGY_TP_PERCENT,
                "sl_percent": settings.STRATEGY_SL_PERCENT,
                "type": "market",
            },
            "max_confirmation_candles": settings.MAX_CONFIRMATION_CANDLES,
            "pending_signals": self._pending_signals,
        }
