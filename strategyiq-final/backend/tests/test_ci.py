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
