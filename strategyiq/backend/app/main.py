from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.constants import SEC_DISCLAIMER
from app.routers import ai, billing, grok, market, portfolio, screener


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="StrategyIQ API",
    description="Commercial Bloomberg Terminal replica for retail investors",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai.router)
app.include_router(screener.router)
app.include_router(portfolio.router)
app.include_router(grok.router)
app.include_router(market.router)
app.include_router(billing.router)


@app.get("/health")
async def health():
    return {"status": "ok", "disclaimer": SEC_DISCLAIMER}


@app.get("/")
async def root():
    return {
        "name": "StrategyIQ",
        "version": "0.1.0",
        "tiers": {
            "beginner": {"price": 0, "queries_per_day": 3, "realtime": False},
            "pro": {"price": 29, "realtime": True, "signals": True},
            "elite": {"price": 79, "custom_agents": True, "port_analytics": True},
        },
        "disclaimer": SEC_DISCLAIMER,
    }
