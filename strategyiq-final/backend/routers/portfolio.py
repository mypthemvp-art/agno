"""PORT <GO> portfolio analytics — holdings table + Celery VaR."""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from constants import SEC_DISCLAIMER, UserTier
from db.auth import get_current_user, log_query, require_tier
from db.models import Holding, Portfolio, PortfolioVarJob, User
from db.session import get_db
from workers.tasks import calculate_portfolio_var

router = APIRouter(prefix="/port", tags=["PORT Analytics"])


class HoldingInput(BaseModel):
    symbol: str
    weight: float = Field(..., ge=0, le=1)
    quantity: float | None = None


class SavePortfolioRequest(BaseModel):
    name: str
    holdings: list[HoldingInput]


@router.post("/save")
def save_portfolio(
    request: SavePortfolioRequest,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(require_tier(UserTier.ELITE)),
    db: Session = Depends(get_db),
):
    total = sum(h.weight for h in request.holdings)
    if abs(total - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail="Weights must sum to 1.0")

    portfolio = Portfolio(user_id=user.id, name=request.name)
    db.add(portfolio)
    db.flush()
    for h in request.holdings:
        db.add(Holding(portfolio_id=portfolio.id, symbol=h.symbol.upper(), weight=h.weight, quantity=h.quantity))
    db.commit()
    return {"id": portfolio.id, "name": request.name, "disclaimer": SEC_DISCLAIMER}


@router.post("/{portfolio_id}/var")
def enqueue_var(
    portfolio_id: int,
    lookback_days: int = 252,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(require_tier(UserTier.ELITE)),
    db: Session = Depends(get_db),
):
    portfolio = (
        db.query(Portfolio)
        .options(selectinload(Portfolio.holdings))
        .filter(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
        .first()
    )
    if not portfolio or not portfolio.holdings:
        raise HTTPException(status_code=404, detail="Portfolio or holdings not found")

    job = PortfolioVarJob(portfolio_id=portfolio_id, celery_task_id="pending", status="pending")
    db.add(job)
    db.flush()
    task = calculate_portfolio_var.delay(portfolio_id, job.id, lookback_days)
    job.celery_task_id = task.id
    db.commit()
    log_query(user, f"/port/{portfolio_id}/var", db)
    return {"job_id": job.id, "celery_task_id": task.id, "status": "pending", "disclaimer": SEC_DISCLAIMER}


@router.get("/var/{job_id}")
def get_var_job(
    job_id: int,
    user: User = Depends(get_current_user),
    tier: UserTier = Depends(require_tier(UserTier.ELITE)),
    db: Session = Depends(get_db),
):
    job = (
        db.query(PortfolioVarJob)
        .join(Portfolio)
        .filter(PortfolioVarJob.id == job_id, Portfolio.user_id == user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = calculate_portfolio_var.AsyncResult(job.celery_task_id)
    if result.ready() and job.status != "completed":
        job.status = "completed" if result.successful() else "failed"
        if result.successful():
            payload = result.result
            job.var_95 = payload.get("var_95")
            job.sharpe_ratio = payload.get("sharpe_ratio")
            job.result_json = json.dumps(payload)
            job.completed_at = datetime.now(UTC)
        db.commit()

    return {
        "job_id": job.id,
        "status": job.status,
        "var_95": job.var_95,
        "sharpe_ratio": job.sharpe_ratio,
        "result": json.loads(job.result_json) if job.result_json else None,
        "disclaimer": SEC_DISCLAIMER,
    }
