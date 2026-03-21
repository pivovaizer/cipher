import pytest

from services.position_history import PositionHistoryService


@pytest.fixture
def history(tmp_path):
    return PositionHistoryService(str(tmp_path / "closed.csv"))


def _make_position(symbol="BTCUSDT", pl=10.0, investment=100.0, duration=30):
    return {
        "close_time": "2026-01-01T00:00:00",
        "symbol": symbol,
        "side": "BUY",
        "entry_price": 50000,
        "exit_price": 51000,
        "quantity": 0.01,
        "investment_amount": investment,
        "profit_loss_usd": pl,
        "profit_loss_percent": (pl / investment) * 100,
        "close_reason": "take_profit" if pl > 0 else "stop_loss",
        "duration_minutes": duration,
        "leverage": 20,
        "tp_price": 51000,
        "sl_price": 49000,
    }


class TestPositionHistory:
    def test_empty_stats(self, history):
        stats = history.get_trading_statistics()
        assert stats["total_positions"] == 0
        assert stats["win_rate_percent"] == 0.0

    def test_add_and_retrieve(self, history):
        history.add_closed_position(_make_position())
        recent = history.get_recent_positions()
        assert len(recent) == 1
        assert recent[0]["symbol"] == "BTCUSDT"

    def test_multiple_positions(self, history):
        for i in range(5):
            history.add_closed_position(_make_position(pl=10.0 * (i + 1)))
        recent = history.get_recent_positions(limit=3)
        assert len(recent) == 3

    def test_get_by_symbol(self, history):
        history.add_closed_position(_make_position("BTCUSDT"))
        history.add_closed_position(_make_position("ETHUSDT"))
        history.add_closed_position(_make_position("BTCUSDT"))
        btc = history.get_positions_by_symbol("BTCUSDT")
        assert len(btc) == 2

    def test_trading_statistics_winning(self, history):
        history.add_closed_position(_make_position(pl=10.0, investment=100.0))
        history.add_closed_position(_make_position(pl=20.0, investment=100.0))
        stats = history.get_trading_statistics()
        assert stats["total_positions"] == 2
        assert stats["winning_positions"] == 2
        assert stats["win_rate_percent"] == 100.0
        assert stats["total_profit_loss_usd"] == 30.0

    def test_trading_statistics_mixed(self, history):
        history.add_closed_position(_make_position(pl=10.0, investment=100.0))
        history.add_closed_position(_make_position(pl=-5.0, investment=100.0))
        stats = history.get_trading_statistics()
        assert stats["winning_positions"] == 1
        assert stats["losing_positions"] == 1
        assert stats["win_rate_percent"] == 50.0
        assert stats["total_profit_loss_usd"] == 5.0

    def test_csv_persistence(self, tmp_path):
        path = str(tmp_path / "closed.csv")
        h1 = PositionHistoryService(path)
        h1.add_closed_position(_make_position())

        h2 = PositionHistoryService(path)
        assert len(h2.get_recent_positions()) == 1
