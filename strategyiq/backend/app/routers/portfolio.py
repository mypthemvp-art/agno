"""Portfolio analytics (PORT) — Sharpe ratio and VaR calculations."""

import json
import math

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.constants import SEC_DISCLAIMER, UserTier
from app.dependencies import get_current_user, log_query, require_tier
from app.integrations.fmp import fmp_client
from app.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db

router = APIRouter(prefix="/port", tags=["PORT Analytics"])


class Holding(BaseModel):
    symbol: str
    weight: float = Field(..., ge=0, le=1, description="Portfolio weight 0-1")


class PortfolioRequest(BaseModel):
    holdings: list[Holding]
    lookback_days: int = Field(252, ge=30, le=756)


class PortfolioMetrics(BaseModel):
    sharpe_ratio: float
    var_95: float
    mean_daily_return: float
    std_daily_return: float
    total_return: float
    holdings: list[dict]
    disclaimer: str = SEC_DISCLAIMER


def calculate_sharpe(daily_returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
    """Sharpe = sqrt(252) * mean(excess_returns) / std(excess_returns)."""
    excess = daily_returns - risk_free_rate / 252
    std = np.std(excess, ddof=1)
    if std == 0:
        return 0.0
    return float(math.sqrt(252) * np.mean(excess) / std)


def calculate_var(daily_returns: np.ndarray, confidence: float = 0.05) -> float:
    """VaR at given confidence level (default 5th percentile)."""
    return float(np.percentile(daily_returns, confidence * 100))


async def _fetch_returns(symbol: str, lookback: int) -> np.ndarray:
    data = await fmp_client.get_historical_prices(symbol)
    historical = data.get("historical", [])
    if len(historical) < 2:
        raise HTTPException(status_code=404, detail=f"Insufficient price history for {symbol}")

    closes = [entry["close"] for entry in historical[: lookback + 1]]
    closes.reverse()
    returns = np.diff(closes) / closes[:-1]
    return returns


@router.post("/analyze", response_model=PortfolioMetrics)
async def analyze_portfolio(
    request: PortfolioRequest,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(require_tier(UserTier.ELITE)),
    db: AsyncSession = Depends(get_db),
):
    """PORT analytics: Sharpe ratio and VaR. Requires Elite tier."""
    total_weight = sum(h.weight for h in request.holdings)
    if abs(total_weight - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail="Holdings weights must sum to 1.0")

    portfolio_returns = None
    holding_details = []

    for holding in request.holdings:
        returns = await _fetch_returns(holding.symbol, request.lookback_days)
        weighted = returns * holding.weight
        if portfolio_returns is None:
            portfolio_returns = weighted
        else:
            min_len = min(len(portfolio_returns), len(weighted))
            portfolio_returns = portfolio_returns[:min_len] + weighted[:min_len]

        holding_details.append({
            "symbol": holding.symbol,
            "weight": holding.weight,
            "mean_return": float(np.mean(returns)),
            "volatility": float(np.std(returns, ddof=1)),
        })

    assert portfolio_returns is not None
    sharpe = calculate_sharpe(portfolio_returns)
    var_95 = calculate_var(portfolio_returns)
    mean_ret = float(np.mean(portfolio_returns))
    std_ret = float(np.std(portfolio_returns, ddof=1))
    total_return = float(np.prod(1 + portfolio_returns) - 1)

    await log_query(user, "/port/analyze", db)

    return PortfolioMetrics(
        sharpe_ratio=round(sharpe, 4),
        var_95=round(var_95, 6),
        mean_daily_return=round(mean_ret, 6),
        std_daily_return=round(std_ret, 6),
        total_return=round(total_return, 4),
        holdings=holding_details,
    )


@router.post("/save")
async def save_portfolio(
    name: str,
    holdings: list[Holding],
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(require_tier(UserTier.ELITE)),
    db: AsyncSession = Depends(get_db),
):
    from app.models import Portfolio

    portfolio = Portfolio(
        user_id=user.id,
        name=name,
        holdings=json.dumps([h.model_dump() for h in holdings]),
    )
    db.add(portfolio)
    await db.commit()
    return {"id": portfolio.id, "name": name, "disclaimer": SEC_DISCLAIMER}
