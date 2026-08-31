# StrategyIQ Final

Commercial Bloomberg Terminal replica for retail investors.

**Financial information only, not financial advice.**

## Structure

```
strategyiq-final/
├── backend/           FastAPI + RAG + Celery workers
├── frontend/          Next.js 14 desktop terminal + mobile PWA
├── infra/             Docker, ECS deploy, Terraform (VPC+RDS+Redis+ECS+ALB)
├── api/               Vercel Python function wrapper
├── vercel.json
└── .cursorrules
```

## Quick Start

```bash
cp backend/.env.example backend/.env
cd infra && docker-compose up
```

- Frontend: http://localhost:3000
- API: http://localhost:8000/docs

## Tiers

| Tier | Price | Features |
|------|-------|----------|
| Beginner | Free | 3 queries/day, delayed |
| Pro | $29/mo | Real-time, signals, Grok |
| Elite | $79/mo | Custom agents, PORT VaR/Sharpe |

## Key Modules

| Module | Path | Description |
|--------|------|-------------|
| EQS | `backend/routers/screener.py` | 50 filters, 15min Redis cache |
| PORT | `backend/routers/portfolio.py` | Holdings table + Celery VaR |
| RAG | `backend/rag/ingest.py` | 500 stocks SEC filings → Pinecone |
| Crypto | `backend/workers/ingest_crypto.py` | 500 crypto → Pinecone |
| AI | `backend/rag/agent.py` | Tier-aware Claude/GPT/Grok |
| Chat | `frontend/app/api/chat/route.ts` | Proxy to `/ai/agent` with JWT |

## Migrations

```bash
cd backend && alembic upgrade head
```

## Deploy

```bash
# Local
cd infra && docker-compose up

# AWS ECS
./infra/deploy-aws.sh staging

# Vercel
vercel deploy

# Terraform
cd infra/terraform && terraform init && terraform apply
```

## Zip Distribution

```bash
zip -r strategyiq-final.zip strategyiq-final -x "*.pyc" "*__pycache__*" "*.git*"
```
