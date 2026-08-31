"""Ingest up to 500 crypto assets from CoinGecko Pro into Pinecone."""

import httpx
from pinecone import Pinecone

from config import settings

COINGECKO_BASE = "https://pro-api.coingecko.com/api/v3"


def _embed(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [item.embedding for item in response.data]


def fetch_top_crypto(limit: int = 500) -> list[dict]:
    coins = []
    pages = (limit + 249) // 250
    headers = {"x-cg-pro-api-key": settings.coingecko_api_key}
    with httpx.Client(timeout=60.0) as client:
        for page in range(1, pages + 1):
            response = client.get(
                f"{COINGECKO_BASE}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 250,
                    "page": page,
                },
                headers=headers,
            )
            response.raise_for_status()
            coins.extend(response.json())
            if len(coins) >= limit:
                break
    return coins[:limit]


def ingest_crypto_universe(limit: int = 500) -> dict:
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(settings.pinecone_index)
    coins = fetch_top_crypto(limit)

    batch_size = 50
    total = 0
    for i in range(0, len(coins), batch_size):
        batch = coins[i : i + batch_size]
        texts = [
            f"{c['id']} {c['symbol']} market_cap={c.get('market_cap')} price={c.get('current_price')}"
            for c in batch
        ]
        embeddings = _embed(texts)
        vectors = [
            {
                "id": f"crypto-{c['id']}",
                "values": emb,
                "metadata": {"symbol": c["symbol"], "text": texts[j][:1000], "asset_class": "crypto"},
            }
            for j, (c, emb) in enumerate(zip(batch, embeddings))
        ]
        index.upsert(vectors=vectors)
        total += len(vectors)

    return {"ingested": total, "limit": limit}
