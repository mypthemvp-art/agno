"""Grok integration for breaking news and trending market queries."""

import httpx

from app.config import settings

GROK_BASE = "https://api.x.ai/v1"


class GrokClient:
    def __init__(self) -> None:
        self.api_key = settings.grok_api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def query_breaking(self, topic: str = "markets") -> dict:
        """Route breaking news queries to Grok."""
        prompt = (
            f"What are the latest breaking developments in {topic}? "
            "Provide factual market-relevant news only. "
            "Financial information only, not financial advice."
        )
        return await self._chat(prompt)

    async def query_trending(self, symbols: list[str] | None = None) -> dict:
        """Route trending market queries to Grok."""
        symbol_str = ", ".join(symbols) if symbols else "global markets"
        prompt = (
            f"What is trending right now for {symbol_str}? "
            "Include sentiment and key catalysts. "
            "Financial information only, not financial advice."
        )
        return await self._chat(prompt)

    async def chat(self, prompt: str) -> dict:
        return await self._chat(prompt)

    async def _chat(self, prompt: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GROK_BASE}/chat/completions",
                headers=self._headers(),
                json={
                    "model": "grok-2",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"query": prompt, "response": content, "source": "grok"}


grok_client = GrokClient()
