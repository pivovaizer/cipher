import pytest

from services.binance_gateway import BinanceGateway


class TestRoundToTick:
    def setup_method(self):
        self.gw = BinanceGateway()

    def test_round_to_tick_basic(self):
        assert self.gw.round_to_tick(100.556, 0.01) == 100.56

    def test_round_to_tick_integer(self):
        assert self.gw.round_to_tick(100.7, 1.0) == 101.0

    def test_round_to_tick_small(self):
        assert self.gw.round_to_tick(0.123456, 0.0001) == 0.1235

    def test_round_to_tick_exact(self):
        assert self.gw.round_to_tick(100.50, 0.50) == 100.5

    def test_round_to_tick_down(self):
        assert self.gw.round_to_tick(100.02, 0.05) == 100.0

    def test_round_to_tick_up(self):
        assert self.gw.round_to_tick(100.03, 0.05) == 100.05

    def test_round_to_tick_four_decimals(self):
        assert self.gw.round_to_tick(1.23456, 0.0010) == pytest.approx(1.235, abs=1e-4)

    def test_round_to_tick_scientific_notation(self):
        # tick_size=1e-06 (VETUSDT) — previously returned 0.0 due to str() giving "1e-06" without "."
        assert self.gw.round_to_tick(0.007554, 1e-06) == pytest.approx(0.007554, abs=1e-6)
        assert self.gw.round_to_tick(0.007630, 1e-06) == pytest.approx(0.007630, abs=1e-6)

    def test_round_to_tick_scientific_notation_nonzero(self):
        # Ensure TP/SL offsets don't collapse to 0 for cheap coins
        assert self.gw.round_to_tick(0.007554, 1e-06) > 0
