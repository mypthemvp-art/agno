"""Portfolio analytics (PORT) — holdings table + Celery VaR tasks."""

import json
import math
from datetime import UTC, datetime

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants import SEC_DISCLAIMER, UserTier
from app.dependencies import get_current_user, get_db, log_query, require_tier
from app.integrations.fmp import fmp_client
from app.models import Holding, Portfolio, PortfolioVarJob, User
from app.tasks.portfolio import calculate_portfolio_var

router = APIRouter(prefix="/port", tags=["PORT Analytics"])


class HoldingInput(BaseModel):
    symbol: str
    weight: float = Field(..., ge=0, le=1, description="Portfolio weight 0-1")
    quantity: float | None = None
    cost_basis: float | None = None


class PortfolioRequest(BaseModel):
    holdings: list[HoldingInput]
    lookback_days: int = Field(252, ge=30, le=756)


class SavePortfolioRequest(BaseModel):
    name: str
    holdings: list[HoldingInput]


class PortfolioMetrics(BaseModel):
    sharpe_ratio: float
    var_95: float
    mean_daily_return: float
    std_daily_return: float
    total_return: float
    holdings: list[dict]
    disclaimer: str = SEC_DISCLAIMER


class VarJobResponse(BaseModel):
    job_id: int
    celery_task_id: str
    status: str
    portfolio_id: int
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
    return np.diff(closes) / closes[:-1]


async def _get_user_portfolio(
    portfolio_id: int, user: User, db: AsyncSession
) -> Portfolio:
    result = await db.execute(
        select(Portfolio)
        .options(selectinload(Portfolio.holdings_rows))
        .where(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


async def _compute_metrics_from_holdings(
    holdings: list[Holding], lookback_days: int
) -> PortfolioMetrics:
    if not holdings:
        raise HTTPException(status_code=400, detail="Portfolio has no holdings")

    total_weight = sum(h.weight for h in holdings)
    if abs(total_weight - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail="Holdings weights must sum to 1.0")

    portfolio_returns = None
    holding_details = []

    for row in holdings:
        returns = await _fetch_returns(row.symbol, lookback_days)
        weighted = returns * row.weight
        if portfolio_returns is None:
            portfolio_returns = weighted
        else:
            min_len = min(len(portfolio_returns), len(weighted))
            portfolio_returns = portfolio_returns[:min_len] + weighted[:min_len]

        holding_details.append({
            "symbol": row.symbol,
            "weight": row.weight,
            "mean_return": float(np.mean(returns)),
            "volatility": float(np.std(returns, ddof=1)),
        })

    assert portfolio_returns is not None
    return PortfolioMetrics(
        sharpe_ratio=round(calculate_sharpe(portfolio_returns), 4),
        var_95=round(calculate_var(portfolio_returns), 6),
        mean_daily_return=round(float(np.mean(portfolio_returns)), 6),
        std_daily_return=round(float(np.std(portfolio_returns, ddof=1)), 6),
        total_return=round(float(np.prod(1 + portfolio_returns) - 1), 4),
        holdings=holding_details,
    )


@router.post("/save")
async def save_portfolio(
    request: SavePortfolioRequest,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(require_tier(UserTier.ELITE)),
    db: AsyncSession = Depends(get_db),
):
    """Save portfolio and persist holdings to the holdings table."""
    total_weight = sum(h.weight for h in request.holdings)
    if abs(total_weight - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail="Holdings weights must sum to 1.0")

    portfolio = Portfolio(
        user_id=user.id,
        name=request.name,
        holdings=json.dumps([h.model_dump() for h in request.holdings]),
    )
    db.add(portfolio)
    await db.flush()

    for h in request.holdings:
        db.add(
            Holding(
                portfolio_id=portfolio.id,
                symbol=h.symbol.upper(),
                weight=h.weight,
                quantity=h.quantity,
                cost_basis=h.cost_basis,
            )
        )

    await db.commit()
    await db.refresh(portfolio)

    return {
        "id": portfolio.id,
        "name": request.name,
        "holdings_count": len(request.holdings),
        "disclaimer": SEC_DISCLAIMER,
    }


@router.get("/{portfolio_id}/holdings")
async def list_holdings(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(require_tier(UserTier.ELITE)),
    db: AsyncSession = Depends(get_db),
):
    """Return holdings rows for a saved portfolio."""
    portfolio = await _get_user_portfolio(portfolio_id, user, db)
    return {
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
        "holdings": [
            {
                "id": h.id,
                "symbol": h.symbol,
                "weight": h.weight,
                "quantity": h.quantity,
                "cost_basis": h.cost_basis,
            }
            for h in portfolio.holdings_rows
        ],
        "disclaimer": SEC_DISCLAIMER,
    }


@router.post("/{portfolio_id}/var", response_model=VarJobResponse)
async def enqueue_var_calculation(
    portfolio_id: int,
    lookback_days: int = 252,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(require_tier(UserTier.ELITE)),
    db: AsyncSession = Depends(get_db),
):
    """Load holdings from DB and dispatch Celery calculate_portfolio_var task."""
    portfolio = await _get_user_portfolio(portfolio_id, user, db)
    if not portfolio.holdings_rows:
        raise HTTPException(status_code=400, detail="Portfolio has no holdings in holdings table")

    job = PortfolioVarJob(
        portfolio_id=portfolio_id,
        celery_task_id="pending",
        status="pending",
    )
    db.add(job)
    await db.flush()

    task = calculate_portfolio_var.delay(portfolio_id, job.id, lookback_days)
    job.celery_task_id = task.id
    await db.commit()
    await db.refresh(job)
    await log_query(user, f"/port/{portfolio_id}/var", db)

    return VarJobResponse(
        job_id=job.id,
        celery_task_id=task.id,
        status=job.status,
        portfolio_id=portfolio_id,
    )


@router.get("/var/{job_id}")
async def get_var_job(
    job_id: int,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(require_tier(UserTier.ELITE)),
    db: AsyncSession = Depends(get_db),
):
    """Poll Celery VaR job status and result."""
    result = await db.execute(
        select(PortfolioVarJob)
        .join(Portfolio)
        .where(PortfolioVarJob.id == job_id, Portfolio.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="VaR job not found")

    celery_result = calculate_portfolio_var.AsyncResult(job.celery_task_id)
    if celery_result.ready() and job.status != "completed":
        job.status = "completed" if celery_result.successful() else "failed"
        if celery_result.successful():
            payload = celery_result.result
            job.var_95 = payload.get("var_95")
            job.sharpe_ratio = payload.get("sharpe_ratio")
            job.result_json = json.dumps(payload)
            job.completed_at = datetime.now(UTC)
        await db.commit()

    return {
        "job_id": job.id,
        "celery_task_id": job.celery_task_id,
        "status": job.status,
        "var_95": job.var_95,
        "sharpe_ratio": job.sharpe_ratio,
        "result": json.loads(job.result_json) if job.result_json else None,
        "disclaimer": SEC_DISCLAIMER,
    }


@router.post("/analyze", response_model=PortfolioMetrics)
async def analyze_portfolio(
    request: PortfolioRequest,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(require_tier(UserTier.ELITE)),
    db: AsyncSession = Depends(get_db),
):
    """Synchronous PORT analytics from request body (ad-hoc, no DB holdings)."""
    total_weight = sum(h.weight for h in request.holdings)
    if abs(total_weight - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail="Holdings weights must sum to 1.0")

    ephemeral = [
        Holding(portfolio_id=0, symbol=h.symbol.upper(), weight=h.weight)
        for h in request.holdings
    ]
    metrics = await _compute_metrics_from_holdings(ephemeral, request.lookback_days)
    await log_query(user, "/port/analyze", db)
    return metrics


@router.post("/{portfolio_id}/analyze", response_model=PortfolioMetrics)
async def analyze_saved_portfolio(
    portfolio_id: int,
    lookback_days: int = 252,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(require_tier(UserTier.ELITE)),
    db: AsyncSession = Depends(get_db),
):
    """Synchronous analysis using holdings table rows."""
    portfolio = await _get_user_portfolio(portfolio_id, user, db)
    metrics = await _compute_metrics_from_holdings(portfolio.holdings_rows, lookback_days)
    await log_query(user, f"/port/{portfolio_id}/analyze", db)
    return metrics
