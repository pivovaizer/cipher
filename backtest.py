"""
Backtest: Nadaraya-Watson strategy — grid search for best params.
Usage: uv run python backtest.py
"""

from datetime import datetime, timedelta, timezone

from binance.client import Client
from config import settings
from services.indicators import klines_to_dataframe, calculate_nadaraya_watson

# ── Config ──────────────────────────────────────────────────────
SYMBOLS = ["BTCUSDT", "BCHUSDT", "BNBUSDT", "XRPUSDT",
           "DOGEUSDT", "ADAUSDT", "ZECUSDT", "AVAXUSDT",
           "HBARUSDT", "LTCUSDT", "ALGOUSDT", "ATOMUSDT",
           "SANDUSDT", "MANAUSDT", "DYDXUSDT",
           "LINKUSDT", "AAVEUSDT", "ICPUSDT", "TRXUSDT"]
TIMEFRAME = "4h"
INVESTMENT = 5.0
LEVERAGE = 30
DEPOSIT = 60.0
MAX_POS = 6
KLINES_LIMIT = 1500  # максимум Binance API
SLIPPAGE_PCT = 0.03  # проскальзывание цены при маркет ордере
TAKER_FEE_PCT = 0.04  # комиссия Binance Futures taker (0.04% за сторону)
TRADE_DAYS = 30  # считать сделки только за последние N дней (0 = всё)
MAX_CONFIRM = 2  # макс свечей подтверждения перед принудительным входом

# ── Configs ──────────────────────────────────────────────────────
CONFIGS = [
    {"bw": 8,  "mult": 3.0, "lb": 500, "tp": 20, "sl": 10, "label": "wide     bw8 m3.0"},
    {"bw": 10, "mult": 4.0, "lb": 500, "tp": 20, "sl": 10, "label": "safe     bw10 m4.0"},
]


# ── Data fetching (raw klines, NW calculated per config) ────────

def fetch_raw_data(client):
    data = {}
    for symbol in SYMBOLS:
        klines = client.futures_klines(symbol=symbol, interval=TIMEFRAME, limit=KLINES_LIMIT)
        df = klines_to_dataframe(klines)
        data[symbol] = df
    return data


# ── Backtest logic ──────────────────────────────────────────────

def backtest_symbol(df, symbol, tp_pct, sl_pct, invest, max_pos, slippage_pct, fee_pct, lookback):
    trades = []
    open_positions = []
    pending_signal = None
    start_idx = lookback + 1

    for i in range(start_idx, len(df)):
        row = df.iloc[i]

        if any(map(lambda c: str(row[c]) == "nan", ("nw_lower", "nw_upper", "nw_line"))):
            continue

        close = row["close"]
        high = row["high"]
        low = row["low"]
        nw_upper = row["nw_upper"]
        nw_lower = row["nw_lower"]
        time = row["open_time"]

        # ── Check open positions for TP/SL ──
        still_open = []
        for pos in open_positions:
            hit_tp = False
            hit_sl = False

            if pos["side"] == "long":
                if high >= pos["tp_price"]:
                    hit_tp = True
                elif low <= pos["sl_price"]:
                    hit_sl = True
            else:
                if low <= pos["tp_price"]:
                    hit_tp = True
                elif high >= pos["sl_price"]:
                    hit_sl = True

            if hit_tp:
                pnl = invest * (tp_pct / 100)
                # Slippage на выход + комиссия на выход (вход уже учтён в entry)
                position_size = pos["entry"] * pos["qty"]
                cost = position_size * (slippage_pct + fee_pct) / 100
                pnl -= cost
                trades.append({
                    "open_time": pos["time"], "close_time": time,
                    "symbol": symbol, "side": pos["side"],
                    "entry": pos["entry"], "exit": pos["tp_price"],
                    "pnl": round(pnl, 4), "result": "TP",
                })
            elif hit_sl:
                pnl = -invest * (sl_pct / 100)
                position_size = pos["entry"] * pos["qty"]
                cost = position_size * (slippage_pct + fee_pct) / 100
                pnl -= cost
                trades.append({
                    "open_time": pos["time"], "close_time": time,
                    "symbol": symbol, "side": pos["side"],
                    "entry": pos["entry"], "exit": pos["sl_price"],
                    "pnl": round(pnl, 4), "result": "SL",
                })
            else:
                still_open.append(pos)

        open_positions = still_open

        # ── Evaluate NW signal ──
        signal = None
        if (high >= nw_lower and low <= nw_lower) or close < nw_lower:
            signal = "long"
        elif (high >= nw_upper and low <= nw_upper) or close > nw_upper:
            signal = "short"

        # ── Pending signal confirmation ──
        should_enter = False
        if signal:
            if pending_signal and pending_signal["signal"] == signal:
                pending_signal["count"] += 1
                # Force entry if max confirmation candles reached
                if pending_signal["count"] >= MAX_CONFIRM:
                    should_enter = True
            else:
                pending_signal = {"signal": signal, "count": 1}
        else:
            # No signal — enter if we had a pending one
            if pending_signal:
                should_enter = True

        if should_enter and pending_signal and len(open_positions) < max_pos:
            side = pending_signal["signal"]
            entry = close
            qty = (invest * LEVERAGE) / entry

            # Slippage + комиссия на вход
            entry_cost_pct = (slippage_pct + fee_pct) / 100
            if side == "long":
                entry *= (1 + entry_cost_pct)  # покупаем дороже
            else:
                entry *= (1 - entry_cost_pct)  # продаём дешевле

            tp_offset = (invest * tp_pct / 100) / qty
            sl_offset = (invest * sl_pct / 100) / qty

            if side == "long":
                tp_price = entry + tp_offset
                sl_price = entry - sl_offset
            else:
                tp_price = entry - tp_offset
                sl_price = entry + sl_offset

            open_positions.append({
                "side": side, "entry": entry, "qty": qty,
                "tp_price": tp_price, "sl_price": sl_price, "time": time,
            })
            pending_signal = None
        elif not signal:
            pending_signal = None

    # Close remaining at last price
    last_close = df.iloc[-1]["close"]
    for pos in open_positions:
        if pos["side"] == "long":
            pnl_per_unit = last_close - pos["entry"]
        else:
            pnl_per_unit = pos["entry"] - last_close
        pnl = pnl_per_unit * pos["qty"]
        position_size = pos["entry"] * pos["qty"]
        cost = position_size * (slippage_pct + fee_pct) / 100
        pnl -= cost
        trades.append({
            "open_time": pos["time"], "close_time": df.iloc[-1]["open_time"],
            "symbol": symbol, "side": pos["side"],
            "entry": pos["entry"], "exit": last_close,
            "pnl": round(pnl, 4), "result": "OPEN",
        })

    return trades


def run_config(raw_data, cfg):
    """Пересчитывает NW с параметрами конфига и прогоняет бэктест."""
    all_trades = []
    for symbol in SYMBOLS:
        df = raw_data[symbol].copy()
        df = calculate_nadaraya_watson(df, bandwidth=cfg["bw"], mult=cfg["mult"], lookback=cfg["lb"])
        trades = backtest_symbol(
            df, symbol, cfg["tp"], cfg["sl"], INVESTMENT, MAX_POS, SLIPPAGE_PCT, TAKER_FEE_PCT, cfg["lb"],
        )
        all_trades.extend(trades)

    # Filter trades by period
    if TRADE_DAYS > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=TRADE_DAYS)
        all_trades = [t for t in all_trades if t["open_time"].replace(tzinfo=timezone.utc) >= cutoff]

    if not all_trades:
        return {"label": cfg["label"], "trades": 0, "tp_hits": 0, "sl_hits": 0,
                "winrate": 0, "total_pnl": 0, "max_dd": 0, "roi": 0,
                "tp_profit": 0, "sl_loss": 0, "all_trades": [], **cfg}

    wins = [t for t in all_trades if t["pnl"] > 0]
    tp_hits = [t for t in all_trades if t["result"] == "TP"]
    sl_hits = [t for t in all_trades if t["result"] == "SL"]
    total_pnl = sum(t["pnl"] for t in all_trades)
    winrate = len(wins) / len(all_trades) * 100

    sorted_trades = sorted(all_trades, key=lambda t: str(t["close_time"]))
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in sorted_trades:
        if t["result"] == "OPEN":
            continue
        running += t["pnl"]
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd

    return {
        "label": cfg["label"], **cfg,
        "trades": len(all_trades),
        "tp_hits": len(tp_hits),
        "sl_hits": len(sl_hits),
        "winrate": winrate,
        "total_pnl": total_pnl,
        "max_dd": max_dd,
        "roi": total_pnl / DEPOSIT * 100,
        "tp_profit": INVESTMENT * cfg["tp"] / 100,
        "sl_loss": INVESTMENT * cfg["sl"] / 100,
        "all_trades": all_trades,
    }


# ── Main ────────────────────────────────────────────────────────

def run_backtest():
    client = Client(settings.BINANCE_API_KEY, settings.BINANCE_API_SECRET)

    print(f"\n{'=' * 95}")
    print(f"  GRID SEARCH: Nadaraya-Watson | {TIMEFRAME} | {len(SYMBOLS)} pairs")
    print(f"  Invest: ${INVESTMENT} x {LEVERAGE}x | MaxPos: {MAX_POS} | Dep: ${DEPOSIT}")
    print(f"  Fees: slippage {SLIPPAGE_PCT}% + taker fee {TAKER_FEE_PCT}% = {SLIPPAGE_PCT + TAKER_FEE_PCT}% per side")
    print(f"  Trade period: last {TRADE_DAYS} days" if TRADE_DAYS > 0 else "  Trade period: all data")
    print(f"  Testing {len(CONFIGS)} configurations...")
    print(f"{'=' * 95}")
    print(f"\nFetching data...")

    raw_data = fetch_raw_data(client)

    first_df = raw_data[SYMBOLS[0]]
    period_start = first_df.iloc[501]["open_time"].date()
    period_end = first_df.iloc[-1]["open_time"].date()

    print(f"\nRunning {len(CONFIGS)} configs...")
    results = []
    for i, cfg in enumerate(CONFIGS):
        r = run_config(raw_data, cfg)
        results.append(r)
        print(f"  [{i+1}/{len(CONFIGS)}] {cfg['label']} -> {r['trades']} trades, ${r['total_pnl']:+.2f}")

    # ── Comparison table ──
    print(f"\n{'=' * 105}")
    print(f"  RESULTS  |  Period: {period_start} -> {period_end}")
    print(f"{'=' * 105}")
    print(f"  {'Config':<22} {'BW':>3} {'Mult':>4} {'TP%':>4} {'SL%':>4} {'Trades':>6} {'TP':>4} {'SL':>4} {'WR%':>6} {'P&L':>9} {'DD':>7} {'ROI':>7}")
    print(f"  {'-' * 103}")

    for r in sorted(results, key=lambda x: x["total_pnl"], reverse=True):
        marker = " <-- BEST" if r == max(results, key=lambda x: x["total_pnl"]) else ""
        print(
            f"  {r['label']:<22} {r['bw']:>3} {r['mult']:>4.1f} {r['tp']:>4} {r['sl']:>4}"
            f" {r['trades']:>6} {r['tp_hits']:>4} {r['sl_hits']:>4}"
            f" {r['winrate']:>5.1f}% ${r['total_pnl']:>+7.2f} ${r['max_dd']:>5.2f}"
            f" {r['roi']:>+6.1f}%{marker}"
        )

    # # ── Top 3 details ──
    # top3 = sorted(results, key=lambda x: x["total_pnl"], reverse=True)[:3]
    # for r in top3:
    #     print(f"\n{'─' * 80}")
    #     print(f"  {r['label']}  |  bw={r['bw']} mult={r['mult']} TP={r['tp']}% SL={r['sl']}%")
    #     print(f"  P&L: ${r['total_pnl']:+.2f}  |  WR: {r['winrate']:.1f}%  |  DD: ${r['max_dd']:.2f}  |  ROI: {r['roi']:+.1f}%")
    #     print(f"{'─' * 80}")
    #     for symbol in SYMBOLS:
    #         sym_trades = [t for t in r["all_trades"] if t["symbol"] == symbol]
    #         if sym_trades:
    #             tp = len([t for t in sym_trades if t["result"] == "TP"])
    #             sl = len([t for t in sym_trades if t["result"] == "SL"])
    #             pnl = sum(t["pnl"] for t in sym_trades)
    #             wr = len([t for t in sym_trades if t["pnl"] > 0]) / len(sym_trades) * 100
    #             print(f"  {symbol:<12} | {len(sym_trades):>3} trades | TP:{tp:>2}  SL:{sl:>2} | WR:{wr:>5.1f}% | P&L: ${pnl:>+7.2f}")

    print(f"\n{'=' * 95}")


if __name__ == "__main__":
    run_backtest()
