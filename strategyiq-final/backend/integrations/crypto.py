"""CoinGecko Pro + Binance WebSocket crypto integrations."""

import asyncio
import json
from typing import AsyncGenerator

import httpx
import websockets

from config import settings
from constants import SEC_DISCLAIMER

COINGECKO_BASE = "https://pro-api.coingecko.com/api/v3"
BINANCE_WS = "wss://stream.binance.com:9443/ws"


class CryptoClient:
    def __init__(self) -> None:
        self.api_key = settings.coingecko_api_key

    def _headers(self) -> dict[str, str]:
        return {"x-cg-pro-api-key": self.api_key}

    async def get_markets(self, per_page: int = 100) -> list:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{COINGECKO_BASE}/coins/markets",
                params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": per_page},
                headers=self._headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_coin(self, coin_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{COINGECKO_BASE}/coins/{coin_id}",
                params={"localization": "false", "tickers": "false", "community_data": "true"},
                headers=self._headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def stream_binance_ticker(self, symbol: str) -> AsyncGenerator[dict, None]:
        stream = f"{symbol.lower()}usdt@trade"
        url = f"{BINANCE_WS}/{stream}"
        async with websockets.connect(url) as ws:
            while True:
                raw = await ws.recv()
                data = json.loads(raw)
                yield {
                    "symbol": symbol.upper(),
                    "price": float(data["p"]),
                    "quantity": float(data["q"]),
                    "ts": data["T"],
                    "disclaimer": SEC_DISCLAIMER,
                }


crypto_client = CryptoClient()


async def demo_stream(symbol: str = "btc", seconds: int = 5) -> list[dict]:
    """Collect ticks for N seconds (for testing)."""
    ticks = []
    try:
        async with asyncio.timeout(seconds):
            async for tick in crypto_client.stream_binance_ticker(symbol):
                ticks.append(tick)
                if len(ticks) >= 10:
                    break
    except TimeoutError:
        pass
    return ticks
