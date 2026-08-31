"""Minimal CI tests for StrategyIQ backend."""

from constants import SEC_DISCLAIMER, TIER_LIMITS, UserTier


def test_sec_disclaimer():
    assert SEC_DISCLAIMER == "Financial information only, not financial advice"


def test_tier_limits_beginner():
    limits = TIER_LIMITS[UserTier.BEGINNER]
    assert limits["queries_per_day"] == 3
    assert limits["realtime"] is False


def test_tier_limits_elite():
    limits = TIER_LIMITS[UserTier.ELITE]
    assert limits["port_analytics"] is True
    assert limits["custom_agents"] is True


def test_screener_filter_count():
    from routers.screener import ScreenerFilters

    assert len(ScreenerFilters.model_fields) == 50


def test_screener_filters_endpoint():
    from routers.screener import list_filters

    payload = list_filters()
    assert payload["filter_count"] == 50
    assert "market_cap_more_than" in payload["filters"]
    assert payload["cache_ttl_seconds"] > 0
    assert "not financial advice" in payload["disclaimer"].lower()


def test_polygon_bars_to_candles():
    from integrations.polygon import bars_to_candles

    candles = bars_to_candles(
        [{"t": 1_704_067_200_000, "o": 10, "h": 12, "l": 9, "c": 11, "v": 1000}]
    )
    assert len(candles) == 1
    assert candles[0]["time"] == "2024-01-01"
    assert candles[0]["open"] == 10
    assert candles[0]["close"] == 11


def test_market_router_exists():
    from routers.market import router

    paths = [route.path for route in router.routes]
    assert any(p.endswith("/history/{symbol}") for p in paths)
    assert any(p.endswith("/quote/{symbol}") for p in paths)
