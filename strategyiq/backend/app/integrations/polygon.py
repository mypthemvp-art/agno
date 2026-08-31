import httpx

from app.config import settings

POLYGON_BASE = "https://api.polygon.io"


class PolygonClient:
    def __init__(self) -> None:
        self.api_key = settings.polygon_api_key

    async def get_ticker_snapshot(self, symbol: str, realtime: bool = True) -> dict:
        async with httpx.AsyncClient() as client:
            url = f"{POLYGON_BASE}/v2/snapshot/locale/us/markets/stocks/tickers/{symbol.upper()}"
            params = {"apiKey": self.api_key}
            if not realtime:
                params["delayed"] = "true"
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()

    async def get_aggregates(
        self, symbol: str, multiplier: int = 1, timespan: str = "day", limit: int = 252
    ) -> dict:
        async with httpx.AsyncClient() as client:
            url = (
                f"{POLYGON_BASE}/v2/aggs/ticker/{symbol.upper()}/range/"
                f"{multiplier}/{timespan}/2020-01-01/2030-12-31"
            )
            response = await client.get(
                url, params={"apiKey": self.api_key, "limit": limit, "sort": "asc"}, timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def search_tickers(self, query: str, limit: int = 10) -> dict:
        async with httpx.AsyncClient() as client:
            url = f"{POLYGON_BASE}/v3/reference/tickers"
            response = await client.get(
                url,
                params={"search": query, "active": "true", "limit": limit, "apiKey": self.api_key},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()


polygon_client = PolygonClient()
