import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class CallQueue:
    def __init__(self, handler: Callable[[dict], Awaitable[None]], maxsize: int = 10):
        self._handler = handler
        self._maxsize = maxsize
        self._whale_q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._regular_q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._tasks: list = []

    async def enqueue(self, task: dict) -> bool:
        q = self._whale_q if task.get("priority") == "whale" else self._regular_q
        try:
            q.put_nowait(task)
            return True
        except asyncio.QueueFull:
            logger.warning(f"Queue full, dropping {task.get('type', 'unknown')} task")
            return False

    async def _worker(self, queue: asyncio.Queue, name: str) -> None:
        while True:
            task = await queue.get()
            if task is None:
                break
            try:
                await self._handler(task)
            except Exception as e:
                logger.error(f"{name} worker error: {e}")
            finally:
                queue.task_done()

    async def start(self) -> None:
        # Two whale workers so real-time alerts don't queue behind scheduled AI tasks
        self._tasks = [
            asyncio.create_task(self._worker(self._whale_q, "whale-1")),
            asyncio.create_task(self._worker(self._whale_q, "whale-2")),
            asyncio.create_task(self._worker(self._regular_q, "regular")),
        ]

    async def stop(self) -> None:
        await self._whale_q.put(None)
        await self._whale_q.put(None)  # one sentinel per whale worker
        await self._regular_q.put(None)
        await asyncio.gather(*self._tasks, return_exceptions=True)
