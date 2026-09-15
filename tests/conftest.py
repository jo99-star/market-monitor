import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "test_key")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
