import asyncio
import json
import logging
import websockets
from typing import Callable, Optional

logger = logging.getLogger(__name__)

WS_URL = "wss://socket.polygon.io/stocks"


class PolygonWebSocket:
    def __init__(self, api_key: str, symbols: list[str]):
        self._key = api_key
        self._symbols = symbols
        self._max_retries = 20
        self.on_tick: Optional[Callable[[dict], None]] = None
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
            # Read until auth_success (Polygon sends a "connected" frame first)
            for _ in range(3):
                raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                msgs = json.loads(raw)
                if any(m.get("status") == "auth_success" for m in msgs):
                    break
                if any(m.get("status") not in ("connected", "auth_success") for m in msgs):
                    raise ConnectionError(f"Auth failed: {msgs}")
            else:
                raise ConnectionError("auth_success not received within 3 frames")
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
        attempt = 0
        while True:
            try:
                await self._connect_once()
                return  # graceful close
            except Exception as e:
                attempt += 1
                logger.warning(f"WS disconnect (attempt {attempt}): {e}")
                await asyncio.sleep(min(delay, self._backoff_max))
                delay = min(delay * 2, self._backoff_max)

    async def run(self) -> None:
        # Outer loop: restart even after repeated failures — never give up
        while True:
            try:
                await self._connect_with_backoff()
            except Exception as e:
                logger.error(f"WS fatal error, restarting in 60s: {e}")
                await asyncio.sleep(60)
