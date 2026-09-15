import json
import logging
from datetime import datetime, timezone
from typing import Optional
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, url: str, ttl: int = 600):
        self._url = url
        self._ttl = ttl
        self._redis: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        self._redis = aioredis.from_url(self._url, decode_responses=True)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()

    async def write_snapshot(self, symbol: str, data: dict) -> None:
        data["written_at"] = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(data)
        try:
            await self._redis.set(f"snapshot:{symbol}:latest", payload, ex=self._ttl)
        except Exception as e:
            logger.error(f"Redis write failed for {symbol}: {e}")

    async def read_snapshot(self, symbol: str) -> Optional[dict]:
        try:
            raw = await self._redis.get(f"snapshot:{symbol}:latest")
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.error(f"Redis read failed for {symbol}: {e}")
            return None

    async def read_latest_or_stale(self, symbol: str) -> Optional[dict]:
        return await self.read_snapshot(symbol)
