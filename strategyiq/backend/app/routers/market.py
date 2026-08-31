"""Market data endpoints using Polygon.io, CoinGecko Pro, and FMP."""

from fastapi import APIRouter, Depends, Query

from app.constants import SEC_DISCLAIMER, TIER_LIMITS, UserTier
from app.dependencies import check_query_limit, get_current_user, get_user_tier, log_query
from app.integrations.coingecko import coingecko_client
from app.integrations.fmp import fmp_client
from app.integrations.polygon import polygon_client
from app.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/quote/{symbol}")
async def get_quote(
    symbol: str,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_query_limit),
):
    realtime = TIER_LIMITS[tier]["realtime"]
    data = await polygon_client.get_ticker_snapshot(symbol, realtime=realtime)
    await log_query(user, f"/market/quote/{symbol}", db)
    return {
        "symbol": symbol.upper(),
        "data": data,
        "realtime": realtime,
        "tier": tier.value,
        "disclaimer": SEC_DISCLAIMER,
    }


@router.get("/history/{symbol}")
async def get_history(
    symbol: str,
    limit: int = Query(252, ge=1, le=1000),
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_query_limit),
):
    data = await polygon_client.get_aggregates(symbol, limit=limit)
    await log_query(user, f"/market/history/{symbol}", db)
    return {"symbol": symbol.upper(), "data": data, "tier": tier.value, "disclaimer": SEC_DISCLAIMER}


@router.get("/profile/{symbol}")
async def get_profile(
    symbol: str,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_query_limit),
):
    data = await fmp_client.get_company_profile(symbol)
    await log_query(user, f"/market/profile/{symbol}", db)
    return {"symbol": symbol.upper(), "profile": data, "tier": tier.value, "disclaimer": SEC_DISCLAIMER}


@router.get("/crypto")
async def get_crypto_markets(
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_query_limit),
):
    data = await coingecko_client.get_coin_markets()
    await log_query(user, "/market/crypto", db)
    return {"markets": data, "tier": tier.value, "disclaimer": SEC_DISCLAIMER}


@router.get("/search")
async def search_symbols(
    q: str = Query(..., min_length=1),
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_query_limit),
):
    data = await polygon_client.search_tickers(q)
    await log_query(user, "/market/search", db)
    return {"query": q, "results": data, "tier": tier.value, "disclaimer": SEC_DISCLAIMER}
