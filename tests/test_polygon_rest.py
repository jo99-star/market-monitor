import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from backend.data.polygon_rest import PolygonREST


@pytest.fixture
def client():
    return PolygonREST(api_key="test_key")


async def test_get_daily_bars_returns_list(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [{"c": 580.0, "h": 585.0, "l": 575.0, "o": 577.0, "v": 80_000_000, "t": 1700000000000}],
        "status": "OK",
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._session, "get", return_value=mock_response) as mock_get:
        mock_get.return_value = mock_response
        # make it awaitable
        async def fake_get(*a, **kw):
            return mock_response
        client._session.get = fake_get
        bars = await client.get_daily_bars("SPY", days=1)

    assert len(bars) == 1
    assert bars[0]["c"] == 580.0


async def test_get_spot_price(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": {"p": 583.40}}
    mock_response.raise_for_status = MagicMock()

    async def fake_get(*a, **kw):
        return mock_response
    client._session.get = fake_get

    price = await client.get_spot_price("SPY")
    assert price == 583.40


async def test_get_news_returns_list(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [{"title": "Fed cuts rates", "published_utc": "2026-09-14T09:00:00Z"}]
    }
    mock_response.raise_for_status = MagicMock()

    async def fake_get(*a, **kw):
        return mock_response
    client._session.get = fake_get

    news = await client.get_news(["SPY", "QQQ"])
    assert len(news) == 1
    assert news[0]["title"] == "Fed cuts rates"


async def test_get_vix_returns_ratio(client):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    # /v2/aggs/ticker/{ticker}/prev returns results array with OHLCV; c = close
    mock_response.json.return_value = {"results": [{"c": 18.0}]}

    call_count = 0

    async def fake_get(url, *a, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # second call = VVIX
            r = MagicMock()
            r.raise_for_status = MagicMock()
            r.json.return_value = {"results": [{"c": 90.0}]}
            return r
        return mock_response

    client._session.get = fake_get

    result = await client.get_vix()
    assert result["vix"] == 18.0
    assert result["vvix"] == 90.0
    assert result["ratio"] == pytest.approx(5.0, rel=0.01)
