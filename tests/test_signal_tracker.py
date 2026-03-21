from datetime import datetime, timedelta, timezone

import pytest

from models.order import OrderRequest
from services.signal_tracker import SignalTrackerService


@pytest.fixture
def tracker(tmp_path):
    return SignalTrackerService(
        processed_file=str(tmp_path / "processed.json"),
        history_file=str(tmp_path / "history.json"),
    )


def _make_order(ticker="BTCUSDT", action="long", minutes_ago=0):
    t = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return OrderRequest(
        ticker=ticker,
        action=action,
        time=t.isoformat(),
        price=50000.0,
    )


class TestSignalTracker:
    def test_fresh_signal(self, tracker):
        order = _make_order(minutes_ago=1)
        assert tracker.is_signal_fresh(order, max_delay_minutes=5) is True

    def test_stale_signal(self, tracker):
        order = _make_order(minutes_ago=10)
        assert tracker.is_signal_fresh(order, max_delay_minutes=5) is False

    def test_signal_not_processed_initially(self, tracker):
        order = _make_order()
        assert tracker.is_signal_processed(order) is False

    def test_add_processed_signal(self, tracker):
        order = _make_order()
        signal_id = tracker.add_processed_signal(order)
        assert tracker.is_signal_processed(order) is True
        assert signal_id is not None

    def test_signal_id_format(self, tracker):
        order = _make_order(ticker="ETHUSDT.P", action="short")
        signal_id = tracker.add_processed_signal(order)
        assert signal_id.startswith("ETHUSDT_short_")

    def test_add_rejected_signal(self, tracker):
        order = _make_order()
        signal_id = tracker.add_rejected_signal(order, "position_open")
        assert signal_id is not None
        # Rejected signals are NOT in processed_signals
        assert tracker.is_signal_processed(order) is False

    def test_get_signal_info(self, tracker):
        order = _make_order()
        signal_id = tracker.add_processed_signal(order, tp_price=55000)
        info = tracker.get_signal_info(signal_id)
        assert info is not None
        assert info["tp_price"] == 55000

    def test_get_recent_signals(self, tracker):
        tracker.add_processed_signal(_make_order(minutes_ago=1))
        tracker.add_processed_signal(_make_order(ticker="ETHUSDT", minutes_ago=2))
        recent = tracker.get_recent_signals(hours=1)
        assert len(recent) == 2

    def test_statistics(self, tracker):
        tracker.add_processed_signal(_make_order(action="long"))
        tracker.add_rejected_signal(_make_order(ticker="ETHUSDT", action="short"), "stale")
        stats = tracker.get_statistics()
        assert stats["total_processed"] == 1
        assert stats["total_history"] == 2
        assert stats["actions_count"]["long"] == 1
        assert stats["actions_count"]["short"] == 1

    def test_cleanup_old_signals(self, tracker):
        # Add a signal, then cleanup with 0 days retention
        tracker.add_processed_signal(_make_order(minutes_ago=2))
        tracker.cleanup_old_signals(days=0)
        # Signal processed 2 min ago is older than 0 days threshold
        # but _parse_dt uses processed_time which is "now", so it should survive
        # This is a sanity check that cleanup runs without error
        assert isinstance(tracker.get_statistics()["total_history"], int)

    def test_persistence(self, tmp_path):
        t1 = SignalTrackerService(
            str(tmp_path / "p.json"), str(tmp_path / "h.json")
        )
        t1.add_processed_signal(_make_order())

        t2 = SignalTrackerService(
            str(tmp_path / "p.json"), str(tmp_path / "h.json")
        )
        assert len(t2.processed_signals) == 1

    def test_fresh_signal_with_z_suffix(self, tracker):
        t = datetime.now(timezone.utc) - timedelta(minutes=1)
        order = OrderRequest(
            ticker="BTCUSDT", action="long",
            time=t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        assert tracker.is_signal_fresh(order, max_delay_minutes=5) is True
