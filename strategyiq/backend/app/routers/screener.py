"""Equity screener (EQS) with 50 filters, cached 15min in Redis."""

import hashlib
import json
from typing import Literal

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.config import settings
from app.constants import SEC_DISCLAIMER, UserTier
from app.dependencies import check_query_limit, get_current_user, get_user_tier, log_query
from app.integrations.fmp import fmp_client
from app.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db

router = APIRouter(prefix="/eqs", tags=["EQS Screener"])

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


class ScreenerFilters(BaseModel):
    """50 equity screener filters mapped to FMP stock-screener API."""

    # Valuation (1-10)
    market_cap_more_than: float | None = Field(None, description="Min market cap")
    market_cap_lower_than: float | None = Field(None, description="Max market cap")
    price_more_than: float | None = Field(None, description="Min price")
    price_lower_than: float | None = Field(None, description="Max price")
    pe_more_than: float | None = Field(None, description="Min P/E ratio")
    pe_lower_than: float | None = Field(None, description="Max P/E ratio")
    pb_more_than: float | None = Field(None, description="Min P/B ratio")
    pb_lower_than: float | None = Field(None, description="Max P/B ratio")
    ps_more_than: float | None = Field(None, description="Min P/S ratio")
    ps_lower_than: float | None = Field(None, description="Max P/S ratio")

    # Profitability (11-18)
    roe_more_than: float | None = Field(None, description="Min ROE")
    roe_lower_than: float | None = Field(None, description="Max ROE")
    roa_more_than: float | None = Field(None, description="Min ROA")
    roa_lower_than: float | None = Field(None, description="Max ROA")
    gross_margin_more_than: float | None = Field(None, description="Min gross margin")
    gross_margin_lower_than: float | None = Field(None, description="Max gross margin")
    net_profit_margin_more_than: float | None = Field(None, description="Min net profit margin")
    net_profit_margin_lower_than: float | None = Field(None, description="Max net profit margin")

    # Growth (19-24)
    revenue_growth_more_than: float | None = Field(None, description="Min revenue growth")
    revenue_growth_lower_than: float | None = Field(None, description="Max revenue growth")
    eps_growth_more_than: float | None = Field(None, description="Min EPS growth")
    eps_growth_lower_than: float | None = Field(None, description="Max EPS growth")
    dividend_yield_more_than: float | None = Field(None, description="Min dividend yield")
    dividend_yield_lower_than: float | None = Field(None, description="Max dividend yield")

    # Financial health (25-32)
    debt_to_equity_more_than: float | None = Field(None, description="Min D/E ratio")
    debt_to_equity_lower_than: float | None = Field(None, description="Max D/E ratio")
    current_ratio_more_than: float | None = Field(None, description="Min current ratio")
    current_ratio_lower_than: float | None = Field(None, description="Max current ratio")
    quick_ratio_more_than: float | None = Field(None, description="Min quick ratio")
    quick_ratio_lower_than: float | None = Field(None, description="Max quick ratio")
    interest_coverage_more_than: float | None = Field(None, description="Min interest coverage")
    interest_coverage_lower_than: float | None = Field(None, description="Max interest coverage")

    # Technical / momentum (33-40)
    beta_more_than: float | None = Field(None, description="Min beta")
    beta_lower_than: float | None = Field(None, description="Max beta")
    volume_more_than: float | None = Field(None, description="Min volume")
    volume_lower_than: float | None = Field(None, description="Max volume")
    price_change_1d_more_than: float | None = Field(None, description="Min 1-day price change %")
    price_change_1d_lower_than: float | None = Field(None, description="Max 1-day price change %")
    price_change_1m_more_than: float | None = Field(None, description="Min 1-month price change %")
    price_change_1m_lower_than: float | None = Field(None, description="Max 1-month price change %")

    # Classification (41-46)
    sector: str | None = Field(None, description="Sector filter")
    industry: str | None = Field(None, description="Industry filter")
    exchange: str | None = Field(None, description="Exchange (NYSE, NASDAQ, etc.)")
    country: str | None = Field(None, description="Country code")
    is_etf: bool | None = Field(None, description="Filter ETFs")
    is_actively_trading: bool | None = Field(None, description="Actively trading only")

    # Sort & pagination (47-50)
    sort_by: Literal[
        "marketCap", "price", "pe", "pb", "dividendYield", "volume", "beta", "change"
    ] = Field("marketCap", description="Sort field")
    sort_order: Literal["asc", "desc"] = Field("desc", description="Sort direction")
    limit: int = Field(50, ge=1, le=500, description="Result limit")
    offset: int = Field(0, ge=0, description="Result offset")

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
        params = {}
        for field_name, fmp_key in mapping.items():
            value = getattr(self, field_name)
            if value is not None:
                params[fmp_key] = value
        return params


def _cache_key(filters: ScreenerFilters) -> str:
    payload = filters.model_dump_json()
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"eqs:screener:{digest}"


@router.post("/screen")
async def run_screener(
    filters: ScreenerFilters,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_query_limit),
):
    """Run equity screener with up to 50 filters. Results cached 15min in Redis."""
    redis = await get_redis()
    key = _cache_key(filters)

    cached = await redis.get(key)
    if cached:
        results = json.loads(cached)
        return {
            "results": results,
            "count": len(results),
            "cached": True,
            "tier": tier.value,
            "disclaimer": SEC_DISCLAIMER,
        }

    fmp_params = filters.to_fmp_params()
    results = await fmp_client.get_stock_screener(fmp_params)

    await redis.setex(key, settings.screener_cache_ttl, json.dumps(results))
    await log_query(user, "/eqs/screen", db)

    return {
        "results": results,
        "count": len(results),
        "cached": False,
        "tier": tier.value,
        "disclaimer": SEC_DISCLAIMER,
    }


@router.get("/filters")
async def list_filters():
    """Return all 50 available screener filter definitions."""
    fields = ScreenerFilters.model_fields
    return {
        "filter_count": len(fields),
        "filters": [
            {"name": name, "description": field.description, "type": str(field.annotation)}
            for name, field in fields.items()
        ],
        "cache_ttl_seconds": settings.screener_cache_ttl,
        "disclaimer": SEC_DISCLAIMER,
    }
