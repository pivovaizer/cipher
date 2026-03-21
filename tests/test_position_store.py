import pytest

from services.position_store import PositionStoreService


@pytest.fixture
def store(tmp_path):
    return PositionStoreService(str(tmp_path / "positions.json"))


class TestPositionStore:
    def test_empty_on_start(self, store):
        assert store.load_positions() == []
        assert store.get_pending_orders() == []
        assert store.get_open_positions() == []

    def test_add_order(self, store):
        store.add_order({"order_id": "1", "symbol": "BTCUSDT", "status": "pending"})
        positions = store.load_positions()
        assert len(positions) == 1
        assert positions[0]["order_id"] == "1"

    def test_add_multiple_orders(self, store):
        store.add_order({"order_id": "1", "status": "pending"})
        store.add_order({"order_id": "2", "status": "open"})
        assert len(store.load_positions()) == 2

    def test_get_pending_orders(self, store):
        store.add_order({"order_id": "1", "status": "pending"})
        store.add_order({"order_id": "2", "status": "open"})
        pending = store.get_pending_orders()
        assert len(pending) == 1
        assert pending[0]["order_id"] == "1"

    def test_get_open_positions(self, store):
        store.add_order({"order_id": "1", "status": "pending"})
        store.add_order({"order_id": "2", "status": "open"})
        open_pos = store.get_open_positions()
        assert len(open_pos) == 1
        assert open_pos[0]["order_id"] == "2"

    def test_update_order_status(self, store):
        store.add_order({"order_id": "100", "status": "pending"})
        updated = store.update_order_status("100", "open", {"tp_price": 55000})
        assert updated is True
        positions = store.load_positions()
        assert positions[0]["status"] == "open"
        assert positions[0]["tp_price"] == 55000

    def test_update_nonexistent_order(self, store):
        store.add_order({"order_id": "1", "status": "pending"})
        updated = store.update_order_status("999", "open")
        assert updated is False

    def test_remove_by_order_id(self, store):
        store.add_order({"order_id": "1", "status": "open"})
        store.add_order({"order_id": "2", "status": "open"})
        removed = store.remove_by_order_id("1")
        assert removed is True
        assert len(store.load_positions()) == 1

    def test_remove_nonexistent_order(self, store):
        store.add_order({"order_id": "1", "status": "open"})
        removed = store.remove_by_order_id("999")
        assert removed is False
        assert len(store.load_positions()) == 1

    def test_remove_by_symbol(self, store):
        store.add_order({"order_id": "1", "symbol": "BTCUSDT", "status": "open"})
        store.add_order({"order_id": "2", "symbol": "BTCUSDT", "status": "open"})
        store.add_order({"order_id": "3", "symbol": "ETHUSDT", "status": "open"})
        count = store.remove_by_symbol("BTCUSDT")
        assert count == 2
        assert len(store.load_positions()) == 1

    def test_add_manual_position(self, store):
        pos = store.add_manual_position("BTCUSDT", "BUY", 0.01, 50000, 10, 20)
        assert pos["symbol"] == "BTCUSDT"
        assert pos["status"] == "open"
        assert pos["manual"] is True
        assert pos["quantity"] == 0.01
        assert len(store.load_positions()) == 1

    def test_close_manual_position(self, store):
        store.add_manual_position("BTCUSDT", "BUY", 0.01, 50000, 10, 20)
        closed = store.close_manual_position("BTCUSDT", 51000, "take_profit")
        assert closed is True
        positions = store.load_positions()
        assert positions[0]["status"] == "closed"
        assert positions[0]["close_price"] == 51000

    def test_close_nonexistent_position(self, store):
        closed = store.close_manual_position("ETHUSDT", 3000, "manual")
        assert closed is False

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "positions.json")
        store1 = PositionStoreService(path)
        store1.add_order({"order_id": "1", "status": "open"})

        store2 = PositionStoreService(path)
        assert len(store2.load_positions()) == 1
