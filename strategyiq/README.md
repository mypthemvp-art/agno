# StrategyIQ

Commercial Bloomberg Terminal replica for retail investors.

**Financial information only, not financial advice.**

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 App Router, Tailwind CSS, TradingView Lightweight Charts |
| Backend | FastAPI, TimescaleDB, Redis, Pinecone, Stripe |
| Market Data | Polygon.io, CoinGecko Pro, FMP (no scraping) |
| AI | Grok for breaking/trending queries |
| Deploy | Docker Compose (local), ECS via `deploy-aws.sh` |

## Subscription Tiers

| Tier | Price | Features |
|------|-------|----------|
| **Beginner** | Free | 3 queries/day, delayed data |
| **Pro** | $29/mo | Real-time data, trading signals, Grok intelligence |
| **Elite** | $79/mo | Custom agents, PORT analytics (Sharpe, VaR) |

## Quick Start

```bash
cp .env.example .env
# Fill in API keys: POLYGON, COINGECKO, FMP, GROK, STRIPE, PINECONE

docker-compose up
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

## Database Migrations

All schema changes via Alembic:

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Architecture

```
strategyiq/
├── frontend/          Next.js 14 terminal UI
│   ├── app/           App Router pages (market, eqs, port, grok, billing)
│   └── components/    PortGo.tsx, TradingChart, Disclaimer
├── backend/           FastAPI API
│   ├── app/
│   │   ├── dependencies.py   get_user_tier, tier gating
│   │   ├── integrations/     polygon, coingecko, fmp, grok
│   │   └── routers/          screener (50 filters), portfolio, market, billing
│   └── alembic/       Database migrations
├── docker-compose.yml
└── deploy-aws.sh      ECS deployment
```

## Key Endpoints

| Module | Endpoint | Tier | Description |
|--------|----------|------|-------------|
| EQS | `POST /eqs/screen` | All | 50-filter screener, 15min Redis cache |
| PORT | `POST /port/{id}/var` | Elite | Async VaR via Celery + holdings table |
| PORT | `GET /port/var/{job_id}` | Elite | Poll Celery VaR job result |
| AI | `POST /ai/agent` | All | Tier-gated agent chat (proxied via `/api/chat`) |
| Grok | `POST /grok/breaking` | All | Breaking news via Grok |
| Market | `GET /market/quote/{symbol}` | All | Polygon.io quotes (delayed for Beginner) |
| Billing | `POST /billing/checkout` | All | Stripe subscription checkout |

## Tier Gating

Backend uses `Depends(get_user_tier)` checking `subscription.active`:

```python
from app.dependencies import get_user_tier, require_tier

@router.post("/port/analyze")
async def analyze(tier: UserTier = Depends(require_tier(UserTier.ELITE))):
    ...
```

## Deploy to Vercel

```bash
# From strategyiq/ — deploys Next.js frontend + FastAPI as Python serverless function
vercel deploy

# Routes:
#   /api/chat          → Next.js route proxy to FastAPI /ai/agent
#   /backend/*         → FastAPI via api/backend/index.py (Mangum)
```

Set `FASTAPI_URL` in Vercel env vars for the chat proxy when FastAPI runs separately.

## Deploy to AWS

```bash
./deploy-aws.sh staging   # or production
```

Requires AWS CLI configured with ECR and ECS access.
