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
