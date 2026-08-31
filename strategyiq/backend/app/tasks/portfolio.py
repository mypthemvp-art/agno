"""Celery tasks for portfolio analytics."""

import json
import math
from datetime import UTC, datetime

import httpx
import numpy as np
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.config import settings
from app.models import Holding, PortfolioVarJob

SYNC_DATABASE_URL = settings.database_url.replace("+asyncpg", "")


def _fetch_sync_returns(symbol: str, lookback: int = 252) -> np.ndarray:
    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol.upper()}"
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, params={"apikey": settings.fmp_api_key})
        response.raise_for_status()
        data = response.json()

    historical = data.get("historical", [])
    if len(historical) < 2:
        raise ValueError(f"Insufficient price history for {symbol}")

    closes = [entry["close"] for entry in historical[: lookback + 1]]
    closes.reverse()
    return np.diff(closes) / closes[:-1]


def _calculate_sharpe(daily_returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
    excess = daily_returns - risk_free_rate / 252
    std = np.std(excess, ddof=1)
    if std == 0:
        return 0.0
    return float(math.sqrt(252) * np.mean(excess) / std)


def _calculate_var(daily_returns: np.ndarray, confidence: float = 0.05) -> float:
    return float(np.percentile(daily_returns, confidence * 100))


@celery_app.task(name="calculate_portfolio_var", bind=True, max_retries=3)
def calculate_portfolio_var(self, portfolio_id: int, job_id: int, lookback_days: int = 252) -> dict:
    """Load holdings from DB, compute VaR and Sharpe, persist job result."""
    engine = create_engine(SYNC_DATABASE_URL)

    with Session(engine) as session:
        job = session.get(PortfolioVarJob, job_id)

        if job:
            job.status = "running"
            job.celery_task_id = self.request.id
            session.commit()

        holdings = session.execute(
            select(Holding).where(Holding.portfolio_id == portfolio_id)
        ).scalars().all()

        if not holdings:
            if job:
                job.status = "failed"
                job.result_json = json.dumps({"error": "No holdings found for portfolio"})
                session.commit()
            return {"error": "No holdings found for portfolio", "portfolio_id": portfolio_id}

        portfolio_returns = None
        holding_details = []

        for row in holdings:
            returns = _fetch_sync_returns(row.symbol, lookback_days)
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
        var_95 = _calculate_var(portfolio_returns)
        sharpe = _calculate_sharpe(portfolio_returns)

        result = {
            "portfolio_id": portfolio_id,
            "var_95": round(var_95, 6),
            "sharpe_ratio": round(sharpe, 4),
            "mean_daily_return": round(float(np.mean(portfolio_returns)), 6),
            "std_daily_return": round(float(np.std(portfolio_returns, ddof=1)), 6),
            "total_return": round(float(np.prod(1 + portfolio_returns) - 1), 4),
            "holdings": holding_details,
            "disclaimer": "Financial information only, not financial advice",
        }

        if job:
            job.status = "completed"
            job.var_95 = var_95
            job.sharpe_ratio = sharpe
            job.result_json = json.dumps(result)
            job.completed_at = datetime.now(UTC)
            session.commit()

        return result
