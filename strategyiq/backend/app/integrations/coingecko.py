import httpx

from app.config import settings

COINGECKO_BASE = "https://pro-api.coingecko.com/api/v3"


class CoinGeckoClient:
    def __init__(self) -> None:
        self.api_key = settings.coingecko_api_key

    def _headers(self) -> dict[str, str]:
        return {"x-cg-pro-api-key": self.api_key}

    async def get_coin_markets(self, vs_currency: str = "usd", per_page: int = 100) -> list:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{COINGECKO_BASE}/coins/markets",
                params={"vs_currency": vs_currency, "order": "market_cap_desc", "per_page": per_page},
                headers=self._headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_coin_history(self, coin_id: str, days: int = 365) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{COINGECKO_BASE}/coins/{coin_id}/market_chart",
                params={"vs_currency": "usd", "days": days},
                headers=self._headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def search_coins(self, query: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{COINGECKO_BASE}/search",
                params={"query": query},
                headers=self._headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()


coingecko_client = CoinGeckoClient()
