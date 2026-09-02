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


def test_jwt_secret_validation():
    import pytest

    from config import validate_jwt_secret

    with pytest.raises(ValueError, match="at least 16"):
        validate_jwt_secret("")
    with pytest.raises(ValueError, match="insecure"):
        validate_jwt_secret("change_this_64_random_chars")
    validate_jwt_secret("test-secret-for-ci-only-not-production")


def test_ai_agent_routes_use_db_tier_only():
    import inspect

    from routers import ai as ai_module

    agent_params = inspect.signature(ai_module.ai_agent).parameters
    stream_params = inspect.signature(ai_module.ai_agent_stream).parameters
    assert "x_user_tier" not in agent_params
    assert "x_user_tier" not in stream_params
