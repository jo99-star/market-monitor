import pytest
import os
from unittest.mock import AsyncMock, patch

# Set dummy env vars before importing app
os.environ.setdefault("POLYGON_API_KEY", "test_key")
os.environ.setdefault("GROQ_API_KEY", "gsk_test")
os.environ.setdefault("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

from httpx import AsyncClient, ASGITransport


async def test_health_returns_ok():
    from backend.main import app
    from backend.api import routes

    mock_cache = AsyncMock()
    mock_cache._redis = AsyncMock()
    mock_cache._redis.ping = AsyncMock(return_value=True)

    routes.cache = mock_cache
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_snapshot_returns_cached_data():
    from backend.main import app
    from backend.api import routes

    mock_data = {"spot": 583.4, "vpoc": 578.0, "written_at": "2026-09-14T10:00:00+00:00"}
    mock_cache = AsyncMock()
    mock_cache.read_snapshot = AsyncMock(return_value=mock_data)
    mock_cache.connect = AsyncMock()
    mock_cache.close = AsyncMock()

    with patch("backend.main._cache", mock_cache):
        routes.cache = mock_cache
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/snapshot?symbol=SPY")

    assert r.status_code == 200
    assert "written_at" in r.json()


async def test_snapshot_returns_503_when_no_data():
    from backend.main import app
    from backend.api import routes

    mock_cache = AsyncMock()
    mock_cache.read_snapshot = AsyncMock(return_value=None)

    routes.cache = mock_cache
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/snapshot?symbol=SPY")

    assert r.status_code == 503
