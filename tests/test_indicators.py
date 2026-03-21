import numpy as np
import pandas as pd
import pytest

from services.indicators import klines_to_dataframe, calculate_nadaraya_watson


def _make_klines(n: int, base_price: float = 100.0):
    """Generate fake klines data (Binance format)."""
    klines = []
    for i in range(n):
        ts = 1700000000000 + i * 60000  # 1min intervals
        o = base_price + np.sin(i * 0.1) * 5
        h = o + 2
        l = o - 2
        c = o + np.cos(i * 0.1) * 3
        vol = 1000 + i
        klines.append([ts, str(o), str(h), str(l), str(c), str(vol),
                        ts + 59999, "0", 10, "0", "0", "0"])
    return klines


class TestKlinesToDataframe:
    def test_correct_columns(self):
        klines = _make_klines(5)
        df = klines_to_dataframe(klines)
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns
        assert "open_time" in df.columns

    def test_numeric_types(self):
        klines = _make_klines(5)
        df = klines_to_dataframe(klines)
        assert df["close"].dtype == float
        assert df["open"].dtype == float
        assert df["high"].dtype == float
        assert df["low"].dtype == float
        assert df["volume"].dtype == float

    def test_length(self):
        klines = _make_klines(10)
        df = klines_to_dataframe(klines)
        assert len(df) == 10

    def test_open_time_is_datetime(self):
        klines = _make_klines(3)
        df = klines_to_dataframe(klines)
        assert pd.api.types.is_datetime64_any_dtype(df["open_time"])


class TestNadarayaWatson:
    def test_adds_columns(self):
        klines = _make_klines(600)
        df = klines_to_dataframe(klines)
        df = calculate_nadaraya_watson(df, bandwidth=8, mult=3, lookback=500)
        assert "nw_line" in df.columns
        assert "nw_upper" in df.columns
        assert "nw_lower" in df.columns

    def test_nan_before_lookback(self):
        klines = _make_klines(600)
        df = klines_to_dataframe(klines)
        df = calculate_nadaraya_watson(df, lookback=500)
        # First 499 rows should be NaN
        assert pd.isna(df["nw_line"].iloc[0])
        assert pd.isna(df["nw_line"].iloc[498])

    def test_values_after_lookback(self):
        klines = _make_klines(600)
        df = klines_to_dataframe(klines)
        df = calculate_nadaraya_watson(df, lookback=500)
        # Row 499 (index) should have a value
        assert not pd.isna(df["nw_line"].iloc[499])

    def test_upper_above_lower(self):
        klines = _make_klines(600)
        df = klines_to_dataframe(klines)
        df = calculate_nadaraya_watson(df, lookback=500)
        valid = df.dropna(subset=["nw_upper", "nw_lower"])
        assert (valid["nw_upper"] >= valid["nw_lower"]).all()

    def test_nw_line_between_bands(self):
        klines = _make_klines(600)
        df = klines_to_dataframe(klines)
        df = calculate_nadaraya_watson(df, lookback=500)
        valid = df.dropna(subset=["nw_line", "nw_upper", "nw_lower"])
        assert (valid["nw_line"] <= valid["nw_upper"]).all()
        assert (valid["nw_line"] >= valid["nw_lower"]).all()

    def test_small_lookback(self):
        klines = _make_klines(20)
        df = klines_to_dataframe(klines)
        df = calculate_nadaraya_watson(df, lookback=10)
        valid = df.dropna(subset=["nw_line"])
        assert len(valid) > 0

    def test_bandwidth_affects_smoothing(self):
        klines = _make_klines(600)
        df1 = calculate_nadaraya_watson(klines_to_dataframe(klines), bandwidth=2, lookback=500)
        df2 = calculate_nadaraya_watson(klines_to_dataframe(klines), bandwidth=20, lookback=500)
        # Different bandwidth should produce different lines
        valid1 = df1["nw_line"].dropna()
        valid2 = df2["nw_line"].dropna()
        assert not np.allclose(valid1.values, valid2.values)
