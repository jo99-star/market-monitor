import pytest
import asyncio
from backend.data.polygon_ws import PolygonWebSocket


async def test_tick_callback_called():
    ws = PolygonWebSocket(api_key="test", symbols=["SPY"])
    received = []
    ws.on_tick = lambda tick: received.append(tick)

    tick = {"ev": "T", "sym": "SPY", "p": 583.40, "s": 100, "t": 1700000000000}
    ws._handle_message([tick])

    assert received[0]["sym"] == "SPY"
    assert received[0]["p"] == 583.40


async def test_non_trade_message_ignored():
    ws = PolygonWebSocket(api_key="test", symbols=["SPY"])
    received = []
    ws.on_tick = lambda tick: received.append(tick)

    ws._handle_message([{"ev": "status", "status": "auth_success"}])
    assert received == []


async def test_reconnects_on_disconnect():
    ws = PolygonWebSocket(api_key="test", symbols=["SPY"])
    connect_calls = []

    async def fake_connect():
        connect_calls.append(1)
        if len(connect_calls) < 2:
            raise ConnectionError("disconnect")

    ws._connect_once = fake_connect
    ws._max_retries = 3
    ws._backoff_base = 0.001  # fast for tests

    await ws._connect_with_backoff()
    assert len(connect_calls) == 2


async def test_raises_after_max_retries():
    ws = PolygonWebSocket(api_key="test", symbols=["SPY"])
    ws._max_retries = 2
    ws._backoff_base = 0.001

    async def always_fail():
        raise ConnectionError("always")

    ws._connect_once = always_fail

    with pytest.raises(ConnectionError):
        await ws._connect_with_backoff()
