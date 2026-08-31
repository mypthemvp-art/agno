import httpx

from app.config import settings

FMP_BASE = "https://financialmodelingprep.com/api/v3"


class FMPClient:
    def __init__(self) -> None:
        self.api_key = settings.fmp_api_key

    async def get_stock_screener(self, params: dict) -> list:
        async with httpx.AsyncClient() as client:
            query = {**params, "apikey": self.api_key}
            response = await client.get(f"{FMP_BASE}/stock-screener", params=query, timeout=30.0)
            response.raise_for_status()
            return response.json()

    async def get_company_profile(self, symbol: str) -> list:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{FMP_BASE}/profile/{symbol.upper()}",
                params={"apikey": self.api_key},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_key_metrics(self, symbol: str, limit: int = 1) -> list:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{FMP_BASE}/key-metrics/{symbol.upper()}",
                params={"apikey": self.api_key, "limit": limit},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_financial_ratios(self, symbol: str, limit: int = 1) -> list:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{FMP_BASE}/ratios/{symbol.upper()}",
                params={"apikey": self.api_key, "limit": limit},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_historical_prices(self, symbol: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{FMP_BASE}/historical-price-full/{symbol.upper()}",
                params={"apikey": self.api_key},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()


fmp_client = FMPClient()
