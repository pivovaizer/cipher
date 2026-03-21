# Best Backtest Configs

## #1 — NW only, 4h (2026-03-17)

```
SYMBOLS  = BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT
TIMEFRAME = 4h
INVESTMENT = 100
LEVERAGE = 20
DEPOSIT = 1000
MAX_POS = 5
TP_PCT = 20  (ROI%)
SL_PCT = 10  (ROI%)
NW_BANDWIDTH = 8
NW_MULT = 3
NW_LOOKBACK = 500
```

**Result (~1 month):**
- Trades: 106 | TP: 58 | SL: 46 | WR: 55.7%
- P&L: +$706.47 | Max DD: $70 | ROI: +70.6%
- Per trade: TP = +$20, SL = -$10

**Notes:** Trend Meter filter (soft/medium/momentum) reduces trades to 2-18 and kills profitability. NW alone works best on 4h.

## #2 — NW grid search winner, 1h (2026-03-17)

```
SYMBOLS  = BTCUSDT, ETHUSDT, BCHUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, ZECUSDT, AVAXUSDT, HBARUSDT, LTCUSDT, ALGOUSDT, ATOMUSDT, SANDUSDT, MANAUSDT, DYDXUSDT, MATICUSDT, LINKUSDT, AAVEUSDT, ICPUSDT, TRXUSDT
TIMEFRAME = 1h
INVESTMENT = 5
LEVERAGE = 20
DEPOSIT = 60
MAX_POS = 5
TP_PCT = 50  (ROI%)
SL_PCT = 20  (ROI%)
NW_BANDWIDTH = 10
NW_MULT = 4.0
NW_LOOKBACK = 500
SLIPPAGE = 0.05%
```

**Result (~1 month, 21 pairs):**
- Trades: 122 | TP: 55 | SL: 65 | WR: 46.7%
- P&L: +$68.46 | Max DD: $16.45 | ROI: +114.1%
- Per trade: TP = +$2.50, SL = -$1.00
- TP:SL ratio = 2.5:1 (breakeven at 28.6% WR)

**Notes:** Grid search best. Wider bands (mult=4.0) + smoother line (bw=10) = fewer but more reliable signals. High TP:SL ratio means profitability even with <50% winrate. Slippage included. 4h gives similar results (~$68, 114% ROI) but no advantage in raising TP/SL further.

## #3 — Safer $1000 dep, 4h + fees (2026-03-17)

```
SYMBOLS  = BTCUSDT, BCHUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, ZECUSDT, AVAXUSDT, HBARUSDT, LTCUSDT, ALGOUSDT, ATOMUSDT, SANDUSDT, MANAUSDT, DYDXUSDT, LINKUSDT, AAVEUSDT, ICPUSDT, TRXUSDT
TIMEFRAME = 4h
INVESTMENT = 100
LEVERAGE = 20
DEPOSIT = 1000
MAX_POS = 6
TP_PCT = 50  (ROI%)
SL_PCT = 20  (ROI%)
NW_BANDWIDTH = 10
NW_MULT = 4.0
NW_LOOKBACK = 500
SLIPPAGE = 0.03%
TAKER_FEE = 0.04%  (total 0.07% per side)
```

**Result (~1 month, 19 pairs, with slippage + fees):**
- Trades: 108 | TP: 54 | SL: 53 | WR: 50.9%
- P&L: +$1517.31 | Max DD: $336.62 | ROI: +151.7%
- Per trade: TP = +$50, SL = -$20
- Max DD = 33.7% of deposit

**Notes:** Removed 2 weak pairs (ETHUSDT, MATICUSDT), increased max positions to 6. Includes real fees (slippage 0.03% + taker 0.04% = 0.07% per side). Chosen over bw8 m4.0 (+$1600, DD $463) — $83 less profit but $127 less drawdown.

## #4 — 30x leverage, TP60/SL20, 4h (2026-03-17)

```
SYMBOLS  = BTCUSDT, BCHUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, ZECUSDT, AVAXUSDT, HBARUSDT, LTCUSDT, ALGOUSDT, ATOMUSDT, SANDUSDT, MANAUSDT, DYDXUSDT, LINKUSDT, AAVEUSDT, ICPUSDT, TRXUSDT
TIMEFRAME = 4h
INVESTMENT = 100
LEVERAGE = 30
DEPOSIT = 1000
MAX_POS = 6
TP_PCT = 60  (ROI%)
SL_PCT = 20  (ROI%)
NW_BANDWIDTH = 10
NW_MULT = 4.0
NW_LOOKBACK = 500
SLIPPAGE = 0.03%
TAKER_FEE = 0.04%  (total 0.07% per side)
```

**Result (~1 month, 19 pairs, with slippage + fees):**
- Trades: 108 | TP: 54 | SL: 53 | WR: 50.9%
- P&L: +$1989.69 | Max DD: $298.83 | ROI: +199.0%
- Per trade: TP = +$60, SL = -$20
- TP:SL ratio = 3:1 (breakeven at 25% WR)
- Max DD = 29.9% of deposit

**Notes:** Leverage 30x + TP 60% = $60 per TP hit. Same pairs/NW params as #3. Higher leverage increases both profits and fees but TP:SL 3:1 ratio keeps it safe — profitable even at 25% WR. DD under 30%.
