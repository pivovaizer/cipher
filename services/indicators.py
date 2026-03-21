import numpy as np
import pandas as pd


def klines_to_dataframe(klines: list[list]) -> pd.DataFrame:
    df = pd.DataFrame(klines, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore",
    ])
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    return df


def _gauss(x: float, h: float) -> float:
    return np.exp(-(x ** 2) / (h * h * 2))


def calculate_nadaraya_watson(
    df: pd.DataFrame,
    bandwidth: float = 8.0,
    mult: float = 3.0,
    lookback: int = 500,
) -> pd.DataFrame:
    """Nadaraya-Watson kernel regression with Gaussian envelope (LuxAlgo)."""
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    n = len(close)

    # Pre-compute Gaussian coefficients
    coefs = np.array([_gauss(i, bandwidth) for i in range(lookback)])
    den = coefs.sum()

    # Kernel regression smoothed line
    nw_line = np.full(n, np.nan)
    for i in range(lookback - 1, n):
        window = close[i - lookback + 1: i + 1][::-1]
        nw_line[i] = np.dot(window, coefs) / den

    # MAE (Mean Absolute Error) for band width
    abs_diff = np.abs(close - nw_line)
    mae = pd.Series(abs_diff).rolling(window=lookback, min_periods=lookback).mean().values * mult

    upper = nw_line + mae
    lower = nw_line - mae

    df["nw_line"] = nw_line
    df["nw_upper"] = upper
    df["nw_lower"] = lower

    return df
