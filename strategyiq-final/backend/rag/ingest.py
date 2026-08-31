"""Ingest 500 stocks SEC filings into Pinecone for RAG retrieval."""

import httpx
from pinecone import Pinecone

from config import settings

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536
FMP_BASE = "https://financialmodelingprep.com/api/v3"


def _get_index():
    pc = Pinecone(api_key=settings.pinecone_api_key)
    return pc.Index(settings.pinecone_index)


def _embed(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]


def fetch_sec_filings(symbol: str, limit: int = 5) -> list[dict]:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{FMP_BASE}/sec_filings/{symbol.upper()}",
            params={"apikey": settings.fmp_api_key, "limit": limit},
        )
        response.raise_for_status()
        return response.json()


def ingest_symbol(symbol: str) -> int:
    filings = fetch_sec_filings(symbol)
    if not filings:
        return 0

    index = _get_index()
    vectors = []
    texts = []
    for i, filing in enumerate(filings):
        text = f"{symbol} {filing.get('type', '10-K')}: {filing.get('link', '')} {filing.get('finalLink', '')}"
        texts.append(text[:8000])
        vectors.append({"id": f"{symbol}-{i}", "metadata": {"symbol": symbol, "type": filing.get("type", "")}})

    embeddings = _embed(texts)
    upsert = []
    for vec, emb, text in zip(vectors, embeddings, texts):
        upsert.append({"id": vec["id"], "values": emb, "metadata": {**vec["metadata"], "text": text[:1000]}})

    index.upsert(vectors=upsert)
    return len(upsert)


def ingest_universe(symbols: list[str]) -> dict:
    results = {}
    for symbol in symbols:
        try:
            results[symbol] = ingest_symbol(symbol)
        except Exception as exc:
            results[symbol] = f"error: {exc}"
    return results


def search_filings(query: str, top_k: int = 5) -> list[dict]:
    if not settings.pinecone_api_key:
        return []
    index = _get_index()
    query_emb = _embed([query])[0]
    results = index.query(vector=query_emb, top_k=top_k, include_metadata=True)
    return [
        {"text": m.metadata.get("text", ""), "symbol": m.metadata.get("symbol", ""), "score": m.score}
        for m in results.matches
    ]


DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "JPM", "V",
    "UNH", "XOM", "LLY", "JNJ", "WMT", "MA", "PG", "AVGO", "HD", "CVX",
]
