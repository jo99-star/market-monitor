import pytest
import asyncio
from backend.ai.call_queue import CallQueue


async def test_whale_and_regular_both_execute():
    executed = []

    async def mock_handler(task):
        executed.append(task["priority"])
        await asyncio.sleep(0)

    q = CallQueue(handler=mock_handler)
    await q.start()

    await q.enqueue({"priority": "regular", "type": "hourly"})
    await q.enqueue({"priority": "whale", "type": "alert"})
    await asyncio.sleep(0.1)
    await q.stop()

    assert "whale" in executed
    assert "regular" in executed


async def test_drops_when_queue_full():
    async def slow_handler(task):
        await asyncio.sleep(0.1)

    q = CallQueue(handler=slow_handler, maxsize=1)
    await q.start()

    results = []
    for i in range(5):
        accepted = await q.enqueue({"priority": "regular", "type": f"t{i}"})
        results.append(accepted)

    await asyncio.sleep(0.5)
    await q.stop()

    # At least some should be dropped
    assert False in results


async def test_enqueue_returns_true_when_accepted():
    async def noop(task):
        pass

    q = CallQueue(handler=noop, maxsize=5)
    await q.start()
    result = await q.enqueue({"priority": "whale", "type": "test"})
    assert result is True
    await q.stop()
