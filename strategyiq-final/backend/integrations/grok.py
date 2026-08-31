"""xAI Grok integration — live X + web search for breaking/trending queries."""

import httpx

from config import settings
from constants import SEC_DISCLAIMER

GROK_BASE = "https://api.x.ai/v1"


class GrokClient:
    def __init__(self) -> None:
        self.api_key = settings.xai_api_key

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def chat(self, prompt: str, search_mode: str = "auto") -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GROK_BASE}/chat/completions",
                headers=self._headers(),
                json={
                    "model": "grok-2",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "search_parameters": {"mode": search_mode},
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"response": content, "source": "grok", "disclaimer": SEC_DISCLAIMER}

    async def breaking(self, topic: str = "markets") -> dict:
        prompt = (
            f"Latest breaking developments in {topic}. Include X/Twitter sentiment. "
            f"{SEC_DISCLAIMER}"
        )
        return await self.chat(prompt, search_mode="on")

    async def trending(self, symbols: list[str] | None = None) -> dict:
        target = ", ".join(symbols) if symbols else "global markets"
        prompt = f"What is trending for {target}? Live web + X search. {SEC_DISCLAIMER}"
        return await self.chat(prompt, search_mode="on")


grok_client = GrokClient()
