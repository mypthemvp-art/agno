"""Market data endpoints — Polygon primary, FMP fallback. Licensed APIs only."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from constants import SEC_DISCLAIMER, TIER_LIMITS, UserTier
from db.auth import check_query_limit, get_current_user, get_user_tier, log_query
from db.models import User
from db.session import get_db
from integrations.polygon import polygon_client

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/history/{symbol}")
def get_history(
    symbol: str,
    limit: int = Query(252, ge=1, le=1000),
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: Session = Depends(get_db),
    _: None = Depends(check_query_limit),
):
    candles = polygon_client.get_aggregates(symbol, limit=limit)
    if not candles:
        raise HTTPException(
            status_code=404,
            detail="No market history available. Configure POLYGON_API_KEY or FMP_API_KEY.",
        )
    log_query(user, f"/market/history/{symbol}", db)
    return {
        "symbol": symbol.upper(),
        "candles": candles,
        "count": len(candles),
        "tier": tier.value,
        "realtime": TIER_LIMITS[tier]["realtime"],
        "disclaimer": SEC_DISCLAIMER,
    }


@router.get("/quote/{symbol}")
def get_quote(
    symbol: str,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: Session = Depends(get_db),
    _: None = Depends(check_query_limit),
):
    realtime = bool(TIER_LIMITS[tier]["realtime"])
    quote = polygon_client.get_quote(symbol, realtime=realtime)
    if quote.get("price") is None and quote.get("source") == "none":
        raise HTTPException(
            status_code=404,
            detail="No quote available. Configure POLYGON_API_KEY or FMP_API_KEY.",
        )
    log_query(user, f"/market/quote/{symbol}", db)
    return {**quote, "tier": tier.value, "disclaimer": SEC_DISCLAIMER}
