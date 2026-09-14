import httpx
from datetime import datetime, timedelta

BASE = "https://api.polygon.io"


class PolygonREST:
    def __init__(self, api_key: str):
        self._key = api_key
        self._session = httpx.AsyncClient(timeout=30)

    def _p(self) -> dict:
        return {"apiKey": self._key}

    async def get_options_snapshot(self, symbol: str, limit: int = 250) -> list[dict]:
        """Fetch full options chain with greeks. Paginates automatically."""
        results = []
        url = f"{BASE}/v3/snapshot/options/{symbol}"
        params = {**self._p(), "limit": limit}
        while url:
            async with self._session.stream("GET", url, params=params) as r:
                r.raise_for_status()
                data = r.json()
            results.extend(data.get("results", []))
            next_url = data.get("next_url")
            url = next_url
            params = {"apiKey": self._key} if next_url else None
        return results

    async def get_daily_bars(self, symbol: str, days: int = 20) -> list[dict]:
        """Fetch last N trading days of OHLCV bars."""
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
        url = f"{BASE}/v2/aggs/ticker/{symbol}/range/1/day/{from_date}/{to_date}"
        r = await self._session.get(url, params={**self._p(), "adjusted": "true", "sort": "asc", "limit": days})
        r.raise_for_status()
        data = r.json()
        return data.get("results", [])[-days:]

    async def get_spot_price(self, symbol: str) -> float:
        """Get latest trade price."""
        url = f"{BASE}/v2/last/trade/{symbol}"
        r = await self._session.get(url, params=self._p())
        r.raise_for_status()
        data = r.json()
        return data["results"]["p"]

    async def get_news(self, symbols: list[str], limit: int = 10) -> list[dict]:
        """Fetch latest news for symbols."""
        tickers = ",".join(symbols)
        url = f"{BASE}/v2/reference/news"
        r = await self._session.get(url, params={**self._p(), "ticker": tickers, "limit": limit, "order": "desc"})
        r.raise_for_status()
        data = r.json()
        return data.get("results", [])

    async def get_vix(self) -> dict:
        """Fetch latest VIX and VVIX spot prices."""
        vix = await self.get_spot_price("VIX")
        vvix = await self.get_spot_price("VVIX")
        return {"vix": vix, "vvix": vvix, "ratio": round(vvix / vix, 3) if vix else None}

    async def close(self):
        await self._session.aclose()
