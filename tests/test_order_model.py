from models.order import OrderRequest


class TestOrderRequest:
    def test_create_basic(self):
        o = OrderRequest(ticker="BTCUSDT", action="long", time="2026-01-01T00:00:00Z")
        assert o.ticker == "BTCUSDT"
        assert o.action == "long"
        assert o.market_order is False

    def test_create_with_all_fields(self):
        o = OrderRequest(
            ticker="ETHUSDT",
            action="short",
            time="2026-01-01T00:00:00Z",
            price=3000.0,
            open=2990.0,
            high=3010.0,
            low=2980.0,
            market_order=True,
        )
        assert o.price == 3000.0
        assert o.market_order is True
        assert o.high == 3010.0

    def test_defaults_none(self):
        o = OrderRequest(ticker="X", action="long", time="t")
        assert o.price is None
        assert o.open is None
        assert o.high is None
        assert o.low is None
