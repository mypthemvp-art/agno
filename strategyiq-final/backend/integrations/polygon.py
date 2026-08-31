"""Polygon.io market data client — licensed API only, never scrape."""

from datetime import UTC, datetime, timedelta

import httpx

from config import settings

POLYGON_BASE = "https://api.polygon.io"
FMP_BASE = "https://financialmodelingprep.com/api/v3"


def _ms_to_date(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%d")


def bars_to_candles(results: list[dict]) -> list[dict]:
    candles = []
    for bar in results:
        candles.append(
            {
                "time": _ms_to_date(int(bar["t"])),
                "open": float(bar["o"]),
                "high": float(bar["h"]),
                "low": float(bar["l"]),
                "close": float(bar["c"]),
                "volume": float(bar.get("v", 0)),
            }
        )
    return candles


class PolygonClient:
    def __init__(self) -> None:
        self.api_key = settings.polygon_api_key
        self.fmp_key = settings.fmp_api_key

    def get_aggregates(self, symbol: str, limit: int = 252) -> list[dict]:
        if self.api_key:
            end = datetime.now(UTC).date()
            start = end - timedelta(days=max(limit * 2, 400))
            url = (
                f"{POLYGON_BASE}/v2/aggs/ticker/{symbol.upper()}/range/"
                f"1/day/{start}/{end}"
            )
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    url,
                    params={"apiKey": self.api_key, "limit": limit, "sort": "asc", "adjusted": "true"},
                )
                response.raise_for_status()
                payload = response.json()
            return bars_to_candles(payload.get("results") or [])

        if self.fmp_key:
            return self._fmp_history(symbol, limit)

        return []

    def get_quote(self, symbol: str, realtime: bool = True) -> dict:
        if self.api_key:
            url = f"{POLYGON_BASE}/v2/snapshot/locale/us/markets/stocks/tickers/{symbol.upper()}"
            params: dict = {"apiKey": self.api_key}
            if not realtime:
                params["delayed"] = "true"
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
            ticker = payload.get("ticker") or {}
            day = ticker.get("day") or {}
            prev = ticker.get("prevDay") or {}
            last = day.get("c") or ticker.get("lastTrade", {}).get("p") or prev.get("c")
            prev_close = prev.get("c")
            change_pct = None
            if last is not None and prev_close:
                change_pct = ((float(last) - float(prev_close)) / float(prev_close)) * 100
            return {
                "symbol": symbol.upper(),
                "price": last,
                "change_pct": change_pct,
                "volume": day.get("v"),
                "open": day.get("o"),
                "high": day.get("h"),
                "low": day.get("l"),
                "prev_close": prev_close,
                "realtime": realtime,
                "source": "polygon",
            }

        if self.fmp_key:
            return self._fmp_quote(symbol, realtime)

        return {"symbol": symbol.upper(), "price": None, "source": "none", "realtime": realtime}

    def _fmp_history(self, symbol: str, limit: int) -> list[dict]:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{FMP_BASE}/historical-price-full/{symbol.upper()}",
                params={"apikey": self.fmp_key},
            )
            response.raise_for_status()
            historical = response.json().get("historical") or []
        candles = []
        for row in reversed(historical[:limit]):
            candles.append(
                {
                    "time": row["date"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume") or 0),
                }
            )
        return candles

    def _fmp_quote(self, symbol: str, realtime: bool) -> dict:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{FMP_BASE}/quote/{symbol.upper()}",
                params={"apikey": self.fmp_key},
            )
            response.raise_for_status()
            rows = response.json()
        row = rows[0] if isinstance(rows, list) and rows else {}
        return {
            "symbol": symbol.upper(),
            "price": row.get("price"),
            "change_pct": row.get("changesPercentage"),
            "volume": row.get("volume"),
            "open": row.get("open"),
            "high": row.get("dayHigh"),
            "low": row.get("dayLow"),
            "prev_close": row.get("previousClose"),
            "realtime": realtime,
            "source": "fmp",
        }


polygon_client = PolygonClient()
