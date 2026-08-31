"""EQS <GO> equity screener with 50 filters, cached 15min in Redis."""

import hashlib
import json
from typing import Literal

import httpx
import redis
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import settings
from constants import SEC_DISCLAIMER, UserTier
from db.auth import check_query_limit, get_current_user, get_user_tier, log_query
from db.models import User
from db.session import get_db

router = APIRouter(prefix="/eqs", tags=["EQS Screener"])
FMP_BASE = "https://financialmodelingprep.com/api/v3"
_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


class ScreenerFilters(BaseModel):
    market_cap_more_than: float | None = None
    market_cap_lower_than: float | None = None
    price_more_than: float | None = None
    price_lower_than: float | None = None
    pe_more_than: float | None = None
    pe_lower_than: float | None = None
    pb_more_than: float | None = None
    pb_lower_than: float | None = None
    ps_more_than: float | None = None
    ps_lower_than: float | None = None
    roe_more_than: float | None = None
    roe_lower_than: float | None = None
    roa_more_than: float | None = None
    roa_lower_than: float | None = None
    gross_margin_more_than: float | None = None
    gross_margin_lower_than: float | None = None
    net_profit_margin_more_than: float | None = None
    net_profit_margin_lower_than: float | None = None
    revenue_growth_more_than: float | None = None
    revenue_growth_lower_than: float | None = None
    eps_growth_more_than: float | None = None
    eps_growth_lower_than: float | None = None
    dividend_yield_more_than: float | None = None
    dividend_yield_lower_than: float | None = None
    debt_to_equity_more_than: float | None = None
    debt_to_equity_lower_than: float | None = None
    current_ratio_more_than: float | None = None
    current_ratio_lower_than: float | None = None
    quick_ratio_more_than: float | None = None
    quick_ratio_lower_than: float | None = None
    interest_coverage_more_than: float | None = None
    interest_coverage_lower_than: float | None = None
    beta_more_than: float | None = None
    beta_lower_than: float | None = None
    volume_more_than: float | None = None
    volume_lower_than: float | None = None
    price_change_1d_more_than: float | None = None
    price_change_1d_lower_than: float | None = None
    price_change_1m_more_than: float | None = None
    price_change_1m_lower_than: float | None = None
    sector: str | None = None
    industry: str | None = None
    exchange: str | None = None
    country: str | None = None
    is_etf: bool | None = None
    is_actively_trading: bool | None = None
    sort_by: Literal["marketCap", "price", "pe", "pb", "dividendYield", "volume", "beta", "change"] = "marketCap"
    sort_order: Literal["asc", "desc"] = "desc"
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)

    def to_fmp_params(self) -> dict:
        mapping = {
            "market_cap_more_than": "marketCapMoreThan",
            "market_cap_lower_than": "marketCapLowerThan",
            "price_more_than": "priceMoreThan",
            "price_lower_than": "priceLowerThan",
            "pe_more_than": "peMoreThan",
            "pe_lower_than": "peLowerThan",
            "pb_more_than": "pbMoreThan",
            "pb_lower_than": "pbLowerThan",
            "ps_more_than": "psMoreThan",
            "ps_lower_than": "psLowerThan",
            "roe_more_than": "roeMoreThan",
            "roe_lower_than": "roeLowerThan",
            "roa_more_than": "roaMoreThan",
            "roa_lower_than": "roaLowerThan",
            "gross_margin_more_than": "grossProfitMarginMoreThan",
            "gross_margin_lower_than": "grossProfitMarginLowerThan",
            "net_profit_margin_more_than": "netProfitMarginMoreThan",
            "net_profit_margin_lower_than": "netProfitMarginLowerThan",
            "revenue_growth_more_than": "revenueGrowthMoreThan",
            "revenue_growth_lower_than": "revenueGrowthLowerThan",
            "eps_growth_more_than": "epsgrowthMoreThan",
            "eps_growth_lower_than": "epsgrowthLowerThan",
            "dividend_yield_more_than": "dividendYieldMoreThan",
            "dividend_yield_lower_than": "dividendYieldLowerThan",
            "debt_to_equity_more_than": "debtToEquityMoreThan",
            "debt_to_equity_lower_than": "debtToEquityLowerThan",
            "current_ratio_more_than": "currentRatioMoreThan",
            "current_ratio_lower_than": "currentRatioLowerThan",
            "quick_ratio_more_than": "quickRatioMoreThan",
            "quick_ratio_lower_than": "quickRatioLowerThan",
            "interest_coverage_more_than": "interestCoverageMoreThan",
            "interest_coverage_lower_than": "interestCoverageLowerThan",
            "beta_more_than": "betaMoreThan",
            "beta_lower_than": "betaLowerThan",
            "volume_more_than": "volumeMoreThan",
            "volume_lower_than": "volumeLowerThan",
            "price_change_1d_more_than": "changeMoreThan",
            "price_change_1d_lower_than": "changeLowerThan",
            "price_change_1m_more_than": "monthChangeMoreThan",
            "price_change_1m_lower_than": "monthChangeLowerThan",
            "sector": "sector",
            "industry": "industry",
            "exchange": "exchange",
            "country": "country",
            "is_etf": "isEtf",
            "is_actively_trading": "isActivelyTrading",
            "sort_by": "sort",
            "sort_order": "order",
            "limit": "limit",
            "offset": "offset",
        }
        return {fmp_key: getattr(self, k) for k, fmp_key in mapping.items() if getattr(self, k) is not None}


def _cache_key(filters: ScreenerFilters) -> str:
    return f"eqs:{hashlib.sha256(filters.model_dump_json().encode()).hexdigest()[:16]}"


def _fmp_screener(params: dict) -> list:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{FMP_BASE}/stock-screener",
            params={**params, "apikey": settings.fmp_api_key},
        )
        response.raise_for_status()
        return response.json()


@router.post("/screen")
def run_screener(
    filters: ScreenerFilters,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: Session = Depends(get_db),
    _: None = Depends(check_query_limit),
):
    r = get_redis()
    key = _cache_key(filters)
    cached = r.get(key)
    if cached:
        results = json.loads(cached)
        return {"results": results, "count": len(results), "cached": True, "tier": tier.value, "disclaimer": SEC_DISCLAIMER}

    results = _fmp_screener(filters.to_fmp_params())
    r.setex(key, settings.screener_cache_ttl, json.dumps(results))
    log_query(user, "/eqs/screen", db)
    return {"results": results, "count": len(results), "cached": False, "tier": tier.value, "disclaimer": SEC_DISCLAIMER}


@router.get("/filters")
def list_filters():
    return {
        "filter_count": len(ScreenerFilters.model_fields),
        "filters": list(ScreenerFilters.model_fields.keys()),
        "cache_ttl_seconds": settings.screener_cache_ttl,
        "disclaimer": SEC_DISCLAIMER,
    }
