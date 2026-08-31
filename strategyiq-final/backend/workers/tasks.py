"""Celery tasks: SEC/crypto ingest, price streaming, portfolio VaR."""

import json
import math
from datetime import UTC, datetime

import httpx
import numpy as np
from sqlalchemy.orm import Session

from config import settings
from db.models import Holding, PortfolioVarJob, PriceTick
from db.session import SessionLocal
from rag.ingest import ingest_universe, DEFAULT_UNIVERSE
from workers.celery_app import celery_app
from workers.ingest_crypto import ingest_crypto_universe

FMP_BASE = "https://financialmodelingprep.com/api/v3"


def _fetch_returns(symbol: str, lookback: int = 252) -> np.ndarray:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{FMP_BASE}/historical-price-full/{symbol.upper()}",
            params={"apikey": settings.fmp_api_key},
        )
        response.raise_for_status()
        data = response.json()
    historical = data.get("historical", [])
    closes = [e["close"] for e in historical[: lookback + 1]]
    closes.reverse()
    return np.diff(closes) / closes[:-1]


@celery_app.task(name="ingest_sec_filings")
def ingest_sec_filings(symbols: list[str] | None = None) -> dict:
    universe = symbols or DEFAULT_UNIVERSE
    return ingest_universe(universe)


@celery_app.task(name="ingest_crypto_to_pinecone")
def ingest_crypto_to_pinecone(limit: int = 500) -> dict:
    return ingest_crypto_universe(limit=limit)


@celery_app.task(name="stream_price_tick")
def stream_price_tick(symbol: str, price: float, volume: float | None = None) -> dict:
    db: Session = SessionLocal()
    try:
        tick = PriceTick(symbol=symbol.upper(), price=price, volume=volume, source="polygon")
        db.add(tick)
        db.commit()
        return {"symbol": symbol, "price": price, "stored": True}
    finally:
        db.close()


@celery_app.task(name="calculate_portfolio_var", bind=True, max_retries=3)
def calculate_portfolio_var(self, portfolio_id: int, job_id: int, lookback_days: int = 252) -> dict:
    db: Session = SessionLocal()
    try:
        job = db.get(PortfolioVarJob, job_id)
        if job:
            job.status = "running"
            job.celery_task_id = self.request.id
            db.commit()

        holdings = db.query(Holding).filter(Holding.portfolio_id == portfolio_id).all()
        if not holdings:
            return {"error": "No holdings found", "portfolio_id": portfolio_id}

        portfolio_returns = None
        details = []
        for row in holdings:
            returns = _fetch_returns(row.symbol, lookback_days)
            weighted = returns * row.weight
            if portfolio_returns is None:
                portfolio_returns = weighted
            else:
                n = min(len(portfolio_returns), len(weighted))
                portfolio_returns = portfolio_returns[:n] + weighted[:n]
            details.append({"symbol": row.symbol, "weight": row.weight})

        assert portfolio_returns is not None
        var_95 = float(np.percentile(portfolio_returns, 5))
        std = np.std(portfolio_returns, ddof=1)
        sharpe = float(math.sqrt(252) * np.mean(portfolio_returns) / std) if std else 0.0

        result = {
            "portfolio_id": portfolio_id,
            "var_95": round(var_95, 6),
            "sharpe_ratio": round(sharpe, 4),
            "holdings": details,
            "disclaimer": "Financial information only, not financial advice",
        }

        if job:
            job.status = "completed"
            job.var_95 = var_95
            job.sharpe_ratio = sharpe
            job.result_json = json.dumps(result)
            job.completed_at = datetime.now(UTC)
            db.commit()

        return result
    finally:
        db.close()
