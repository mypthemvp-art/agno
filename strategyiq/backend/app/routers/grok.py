"""Grok-powered breaking news and trending market queries."""

from fastapi import APIRouter, Depends

from app.constants import SEC_DISCLAIMER, UserTier
from app.dependencies import check_query_limit, get_current_user, get_user_tier, log_query
from app.integrations.grok import grok_client
from app.models import User
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db

router = APIRouter(prefix="/grok", tags=["Grok Intelligence"])


class BreakingQuery(BaseModel):
    topic: str = "markets"


class TrendingQuery(BaseModel):
    symbols: list[str] | None = None


@router.post("/breaking")
async def breaking_news(
    query: BreakingQuery,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_query_limit),
):
    """Route breaking news queries to Grok integration."""
    result = await grok_client.query_breaking(query.topic)
    await log_query(user, "/grok/breaking", db)
    return {**result, "tier": tier.value, "disclaimer": SEC_DISCLAIMER}


@router.post("/trending")
async def trending_markets(
    query: TrendingQuery,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(get_user_tier),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_query_limit),
):
    """Route trending market queries to Grok integration."""
    result = await grok_client.query_trending(query.symbols)
    await log_query(user, "/grok/trending", db)
    return {**result, "tier": tier.value, "disclaimer": SEC_DISCLAIMER}
