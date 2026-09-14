import asyncio
import json
import logging
import websockets
from typing import Callable

logger = logging.getLogger(__name__)

WS_URL = "wss://socket.polygon.io/stocks"


class PolygonWebSocket:
    def __init__(self, api_key: str, symbols: list[str]):
        self._key = api_key
        self._symbols = symbols
        self._max_retries = 20
        self.on_tick: Callable[[dict], None] | None = None
        self._backoff_base = 1.0
        self._backoff_max = 60.0

    def _handle_message(self, messages: list[dict]) -> None:
        for msg in messages:
            if msg.get("ev") == "T" and self.on_tick:
                self.on_tick(msg)

    async def _connect_once(self) -> None:
        subs = ",".join(f"T.{s}" for s in self._symbols)
        async with websockets.connect(WS_URL) as ws:
            await ws.send(json.dumps({"action": "auth", "params": self._key}))
            await ws.send(json.dumps({"action": "subscribe", "params": subs}))
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    self._handle_message(json.loads(raw))
                except asyncio.TimeoutError:
                    logger.warning("WebSocket heartbeat timeout, reconnecting")
                    raise ConnectionError("heartbeat timeout")

    async def _connect_with_backoff(self) -> None:
        delay = self._backoff_base
        for attempt in range(self._max_retries):
            try:
                await self._connect_once()
                return  # graceful close — stop reconnecting

            except Exception as e:
                logger.warning(f"WS disconnect (attempt {attempt + 1}): {e}")
                if attempt == self._max_retries - 1:
                    raise
                await asyncio.sleep(min(delay, self._backoff_max))
                delay = min(delay * 2, self._backoff_max)

    async def run(self) -> None:
        await self._connect_with_backoff()
