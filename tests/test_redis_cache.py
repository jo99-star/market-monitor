import pytest
import json
from unittest.mock import AsyncMock
from backend.cache.redis_cache import RedisCache


async def test_write_uses_atomic_rename():
    cache = RedisCache(url="redis://localhost:6379", ttl=600)
    mock_redis = AsyncMock()
    cache._redis = mock_redis

    await cache.write_snapshot("SPY", {"vpoc": 580.0, "spot": 583.0})

    calls = mock_redis.set.call_args_list
    assert any("tmp" in str(c) for c in calls), "Expected tmp key write"
    mock_redis.rename.assert_called_once()


async def test_read_returns_parsed_snapshot():
    cache = RedisCache(url="redis://localhost:6379", ttl=600)
    payload = {"vpoc": 580.0, "written_at": "2026-09-14T09:15:00"}
    mock_redis = AsyncMock()
    mock_redis.get.return_value = json.dumps(payload)
    cache._redis = mock_redis

    result = await cache.read_snapshot("SPY")
    assert result["vpoc"] == 580.0
    assert result["written_at"] == "2026-09-14T09:15:00"


async def test_read_returns_none_when_missing():
    cache = RedisCache(url="redis://localhost:6379", ttl=600)
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    cache._redis = mock_redis

    result = await cache.read_snapshot("SPY")
    assert result is None


async def test_write_adds_written_at():
    cache = RedisCache(url="redis://localhost:6379", ttl=600)
    mock_redis = AsyncMock()
    cache._redis = mock_redis

    data = {"vpoc": 580.0}
    await cache.write_snapshot("SPY", data)

    written_payload = json.loads(mock_redis.set.call_args[0][1])
    assert "written_at" in written_payload
