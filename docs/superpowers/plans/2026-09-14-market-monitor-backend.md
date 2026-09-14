# 大盘监测系统 — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend for SPY/QQQ real-time market monitoring: Polygon data ingestion, large order detection, chip distribution (VPOC/GEX), options flow, sentiment, Claude AI interpretation, Discord notifications, Redis snapshot, and scheduled jobs.

**Architecture:** FastAPI on Railway Hobby with Polygon WebSocket for real-time tick data and REST for options chain / news. Redis (separate Railway service) stores atomic snapshots. AsyncIOScheduler fires pre-market (9:15), hourly, and close (16:00) jobs. Claude API calls route through a dual-worker asyncio queue (Whale worker + regular worker).

**Tech Stack:** Python 3.11, FastAPI, uvicorn, APScheduler[asyncio], redis[asyncio], anthropic, praw, httpx, websockets, pydantic-settings, pytest, pytest-asyncio

---

## File Map

```
market-monitor/
├── backend/
│   ├── main.py                      # FastAPI app, lifespan, CORS, startup
│   ├── config.py                    # Settings via pydantic-settings
│   ├── data/
│   │   ├── polygon_rest.py          # Polygon REST client (options, aggs, news, VIX)
│   │   ├── polygon_ws.py            # WebSocket client + exponential backoff reconnect
│   │   └── economic_calendar.py    # Economic calendar fetcher (Trading Economics)
│   ├── analysis/
│   │   ├── block_detector.py        # 30s sliding window large order aggregation
│   │   ├── chip_profile.py          # VPOC/VAH/VAL ($0.10 buckets) + GEX + Max Pain
│   │   ├── options_flow.py          # Sweep/Block detection (FlowScanner port)
│   │   └── sentiment.py            # OI PCR, Volume PCR, Reddit, news
│   ├── ai/
│   │   ├── call_queue.py            # Dual asyncio.Queue workers (Whale + regular)
│   │   └── interpreter.py          # Claude API structured interpretation
│   ├── notifier/
│   │   └── discord.py              # Discord webhook (4 message types)
│   ├── cache/
│   │   └── redis_cache.py          # Atomic tmp→RENAME snapshot writes
│   ├── scheduler.py                 # AsyncIOScheduler 9:15 / hourly / 16:00
│   └── api/
│       └── routes.py               # /api/snapshot, /api/health endpoints
├── tests/
│   ├── conftest.py
│   ├── test_block_detector.py
│   ├── test_chip_profile.py
│   ├── test_options_flow.py
│   ├── test_sentiment.py
│   ├── test_interpreter.py
│   ├── test_redis_cache.py
│   └── test_routes.py
├── .env.example
├── requirements.txt
└── railway.json
```

---

## Task 1: Project Setup

**Files:**
- Create: `backend/` (directory structure)
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p backend/{data,analysis,ai,notifier,cache,api}
mkdir -p tests
touch backend/__init__.py backend/data/__init__.py backend/analysis/__init__.py
touch backend/ai/__init__.py backend/notifier/__init__.py backend/cache/__init__.py backend/api/__init__.py
touch tests/__init__.py
```

- [ ] **Step 2: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic-settings==2.4.0
httpx==0.27.2
websockets==13.0.1
redis[asyncio]==5.0.8
anthropic==0.34.2
apscheduler==3.10.4
praw==7.7.1
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-httpx==0.32.0
python-dotenv==1.0.1
scipy==1.14.1
numpy==2.1.1
```

- [ ] **Step 3: Install dependencies**

```bash
cd market-monitor
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 4: Create .env.example**

```
POLYGON_API_KEY=your_polygon_key
ANTHROPIC_API_KEY=your_anthropic_key
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
REDIS_URL=redis://localhost:6379
NEWSAPI_KEY=optional
REDDIT_CLIENT_ID=optional
REDDIT_CLIENT_SECRET=optional
REDDIT_USER_AGENT=market-monitor/1.0
```

- [ ] **Step 5: Create tests/conftest.py**

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "test_key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_anthropic")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example tests/conftest.py backend/
git commit -m "feat: initialize backend project structure"
```

---

## Task 2: Config

**Files:**
- Create: `backend/config.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config.py
from backend.config import Settings

def test_settings_defaults():
    s = Settings(
        polygon_api_key="key",
        anthropic_api_key="akey",
        discord_webhook_url="https://discord.com/test",
        redis_url="redis://localhost:6379",
    )
    assert s.symbols == ["SPY", "QQQ"]
    assert s.stock_whale_threshold == 50_000_000
    assert s.options_whale_threshold == 1_000_000
    assert s.block_window_seconds == 30
    assert s.options_refresh_minutes == 10
    assert s.gex_neutral_threshold == 500_000_000
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_config.py -v
```
Expected: `ModuleNotFoundError: No module named 'backend.config'`

- [ ] **Step 3: Implement config.py**

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    polygon_api_key: str
    anthropic_api_key: str
    discord_webhook_url: str
    redis_url: str
    newsapi_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "market-monitor/1.0"
    symbols: list[str] = ["SPY", "QQQ"]

    # Thresholds
    stock_alert_threshold: float = 20_000_000
    stock_whale_threshold: float = 50_000_000
    options_alert_threshold: float = 500_000
    options_whale_threshold: float = 1_000_000
    gex_neutral_threshold: float = 500_000_000
    block_window_seconds: int = 30
    options_refresh_minutes: int = 10
    snapshot_ttl_seconds: int = 600
    discord_cooldown_seconds: int = 300

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_config.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/config.py tests/test_config.py
git commit -m "feat: add settings config with pydantic-settings"
```

---

## Task 3: Polygon REST Client

**Files:**
- Create: `backend/data/polygon_rest.py`
- Create: `tests/test_polygon_rest.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_polygon_rest.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.data.polygon_rest import PolygonREST

@pytest.mark.asyncio
async def test_get_options_snapshot_returns_results():
    client = PolygonREST(api_key="test_key")
    mock_response = {
        "results": [
            {
                "details": {"strike_price": 580, "contract_type": "call", "expiration_date": "2026-09-20"},
                "greeks": {"gamma": 0.05, "delta": 0.6, "theta": -0.3, "vega": 0.2},
                "implied_volatility": 0.18,
                "open_interest": 5000,
                "day": {"volume": 1200},
            }
        ],
        "status": "OK"
    }
    with patch.object(client._session, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(
            json=AsyncMock(return_value=mock_response),
            raise_for_status=AsyncMock()
        ))
        results = await client.get_options_snapshot("SPY")
    assert len(results) == 1
    assert results[0]["greeks"]["gamma"] == 0.05

@pytest.mark.asyncio
async def test_get_daily_bars_returns_list():
    client = PolygonREST(api_key="test_key")
    mock_response = {
        "results": [{"c": 580.0, "h": 585.0, "l": 575.0, "o": 577.0, "v": 80000000, "t": 1700000000000}],
        "status": "OK"
    }
    with patch.object(client._session, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(
            json=AsyncMock(return_value=mock_response),
            raise_for_status=AsyncMock()
        ))
        bars = await client.get_daily_bars("SPY", days=20)
    assert len(bars) == 1
    assert bars[0]["c"] == 580.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_polygon_rest.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement polygon_rest.py**

```python
import httpx
from datetime import datetime, timedelta

BASE = "https://api.polygon.io"

class PolygonREST:
    def __init__(self, api_key: str):
        self._key = api_key
        self._session = httpx.AsyncClient(timeout=30)

    def _p(self) -> dict:
        return {"apiKey": self._key}

    async def get_options_snapshot(self, symbol: str, limit: int = 250) -> list[dict]:
        """Fetch full options chain with greeks. Paginates automatically."""
        results = []
        url = f"{BASE}/v3/snapshot/options/{symbol}"
        params = {**self._p(), "limit": limit}
        while url:
            async with self._session.get(url, params=params) as r:
                r.raise_for_status()
                data = r.json()
            results.extend(data.get("results", []))
            next_url = data.get("next_url")
            url = next_url
            params = {"apiKey": self._key} if next_url else None
        return results

    async def get_daily_bars(self, symbol: str, days: int = 20) -> list[dict]:
        """Fetch last N trading days of OHLCV bars."""
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
        url = f"{BASE}/v2/aggs/ticker/{symbol}/range/1/day/{from_date}/{to_date}"
        async with self._session.get(url, params={**self._p(), "adjusted": "true", "sort": "asc", "limit": days}) as r:
            r.raise_for_status()
            data = r.json()
        return data.get("results", [])[-days:]

    async def get_spot_price(self, symbol: str) -> float:
        """Get latest trade price."""
        url = f"{BASE}/v2/last/trade/{symbol}"
        async with self._session.get(url, params=self._p()) as r:
            r.raise_for_status()
            data = r.json()
        return data["results"]["p"]

    async def get_news(self, symbols: list[str], limit: int = 10) -> list[dict]:
        """Fetch latest news for symbols."""
        tickers = ",".join(symbols)
        url = f"{BASE}/v2/reference/news"
        async with self._session.get(url, params={**self._p(), "ticker": tickers, "limit": limit, "order": "desc"}) as r:
            r.raise_for_status()
            data = r.json()
        return data.get("results", [])

    async def close(self):
        await self._session.aclose()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_polygon_rest.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/data/polygon_rest.py tests/test_polygon_rest.py
git commit -m "feat: add Polygon REST client with pagination"
```

---

## Task 4: Polygon WebSocket Client

**Files:**
- Create: `backend/data/polygon_ws.py`
- Create: `tests/test_polygon_ws.py`

Domain note: Polygon WebSocket sends JSON messages. `T.*` = trades channel for all symbols. Messages arrive as lists. Connection requires auth via `{"action":"auth","params":"API_KEY"}` then subscribe via `{"action":"subscribe","params":"T.SPY,T.QQQ"}`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_polygon_ws.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from backend.data.polygon_ws import PolygonWebSocket

@pytest.mark.asyncio
async def test_reconnects_on_disconnect():
    ws = PolygonWebSocket(api_key="test", symbols=["SPY"])
    connect_calls = []

    async def fake_connect():
        connect_calls.append(1)
        if len(connect_calls) == 1:
            raise ConnectionError("disconnect")

    ws._connect_once = fake_connect
    ws._max_retries = 2

    with pytest.raises(ConnectionError):
        await ws._connect_with_backoff()

    assert len(connect_calls) == 2

@pytest.mark.asyncio
async def test_tick_callback_called():
    ws = PolygonWebSocket(api_key="test", symbols=["SPY"])
    received = []
    ws.on_tick = lambda tick: received.append(tick)

    tick = {"ev": "T", "sym": "SPY", "p": 583.40, "s": 100, "t": 1700000000000}
    ws._handle_message([tick])

    assert received[0]["sym"] == "SPY"
    assert received[0]["p"] == 583.40
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_polygon_ws.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement polygon_ws.py**

```python
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
            last_msg_time = asyncio.get_event_loop().time()
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    last_msg_time = asyncio.get_event_loop().time()
                    self._handle_message(json.loads(raw))
                except asyncio.TimeoutError:
                    if asyncio.get_event_loop().time() - last_msg_time > 30:
                        logger.warning("WebSocket heartbeat timeout, reconnecting")
                        raise ConnectionError("heartbeat timeout")

    async def _connect_with_backoff(self) -> None:
        delay = self._backoff_base
        for attempt in range(self._max_retries):
            try:
                await self._connect_once()
                delay = self._backoff_base
            except Exception as e:
                logger.warning(f"WS disconnect (attempt {attempt+1}): {e}")
                if attempt == self._max_retries - 1:
                    raise
                await asyncio.sleep(min(delay, self._backoff_max))
                delay = min(delay * 2, self._backoff_max)

    async def run(self) -> None:
        await self._connect_with_backoff()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_polygon_ws.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/data/polygon_ws.py tests/test_polygon_ws.py
git commit -m "feat: add Polygon WebSocket client with exponential backoff"
```

---

## Task 5: Block Detector

**Files:**
- Create: `backend/analysis/block_detector.py`
- Create: `tests/test_block_detector.py`

Domain note: A "block trade" is a very large order. Because SPY is so liquid, institutions often split orders across many smaller executions (iceberg orders). We aggregate same-direction ticks within a 30-second sliding window. Direction uses the `conditions` field: condition 41 = bought on ask (buy aggressor), condition 38 = sold on bid (sell aggressor). If no condition, use tick rule (price ≥ previous price → buy).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_block_detector.py
import pytest
import time
from backend.analysis.block_detector import BlockDetector

def make_tick(sym, price, size, side="buy", ts_offset=0):
    return {
        "ev": "T", "sym": sym, "p": price, "s": size,
        "t": int((time.time() + ts_offset) * 1000),
        "_side": side
    }

def test_aggregates_same_direction_within_window():
    det = BlockDetector(window_seconds=30, whale_threshold=50_000_000, alert_threshold=20_000_000)
    # 3 buy ticks, each $10M notional → total $30M → triggers alert
    for _ in range(3):
        det.ingest(make_tick("SPY", 500.0, 20_000, "buy"))
    alerts = det.flush_alerts()
    assert len(alerts) == 1
    assert alerts[0]["notional"] >= 20_000_000
    assert alerts[0]["side"] == "buy"

def test_does_not_aggregate_opposite_directions():
    det = BlockDetector(window_seconds=30, whale_threshold=50_000_000, alert_threshold=20_000_000)
    det.ingest(make_tick("SPY", 500.0, 20_000, "buy"))
    det.ingest(make_tick("SPY", 500.0, 20_000, "sell"))
    alerts = det.flush_alerts()
    assert len(alerts) == 0  # neither side reaches $20M alone

def test_expires_old_ticks():
    det = BlockDetector(window_seconds=1, whale_threshold=50_000_000, alert_threshold=5_000_000)
    det.ingest(make_tick("SPY", 500.0, 5_000, "buy", ts_offset=-2))  # 2s ago → expired
    det.ingest(make_tick("SPY", 500.0, 5_000, "buy"))  # now
    alerts = det.flush_alerts()
    # Only the fresh tick: 5000 × 500 = $2.5M < $5M threshold
    assert len(alerts) == 0

def test_determines_side_from_tick_rule():
    det = BlockDetector(window_seconds=30, whale_threshold=50_000_000, alert_threshold=1_000)
    tick1 = {"ev": "T", "sym": "SPY", "p": 583.0, "s": 10, "t": int(time.time() * 1000)}
    tick2 = {"ev": "T", "sym": "SPY", "p": 584.0, "s": 10, "t": int(time.time() * 1000) + 100}
    det.ingest(tick1)
    det.ingest(tick2)
    # tick2 price > tick1 price → buy
    assert det._last_price["SPY"] == 584.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_block_detector.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement block_detector.py**

```python
import time
from collections import defaultdict
from dataclasses import dataclass, field

BUY_CONDITIONS = {41}   # Polygon: bought on ask
SELL_CONDITIONS = {38}  # Polygon: sold on bid

@dataclass
class _Window:
    buy_notional: float = 0.0
    sell_notional: float = 0.0
    ticks: list = field(default_factory=list)

class BlockDetector:
    def __init__(self, window_seconds: int, whale_threshold: float, alert_threshold: float):
        self._window = window_seconds
        self._whale = whale_threshold
        self._alert = alert_threshold
        self._windows: dict[str, _Window] = defaultdict(_Window)
        self._last_price: dict[str, float] = {}
        self._pending_alerts: list[dict] = []
        self._seen: set = set()

    def _determine_side(self, tick: dict) -> str:
        conditions = set(tick.get("c", []) or [])
        if conditions & BUY_CONDITIONS:
            return "buy"
        if conditions & SELL_CONDITIONS:
            return "sell"
        # Tick rule fallback
        sym = tick["sym"]
        prev = self._last_price.get(sym, tick["p"])
        side = "buy" if tick["p"] >= prev else "sell"
        self._last_price[sym] = tick["p"]
        return side

    def _expire(self, sym: str) -> None:
        now_ms = time.time() * 1000
        cutoff = now_ms - self._window * 1000
        w = self._windows[sym]
        fresh = [t for t in w.ticks if t["t"] >= cutoff]
        w.buy_notional = sum(t["p"] * t["s"] for t in fresh if t["_side"] == "buy")
        w.sell_notional = sum(t["p"] * t["s"] for t in fresh if t["_side"] == "sell")
        w.ticks = fresh

    def ingest(self, tick: dict) -> None:
        dedup_key = (tick["sym"], tick["t"], tick["p"], tick["s"])
        if dedup_key in self._seen:
            return
        self._seen.add(dedup_key)
        if len(self._seen) > 10_000:
            self._seen = set(list(self._seen)[-5_000:])

        sym = tick["sym"]
        side = tick.get("_side") or self._determine_side(tick)
        tick["_side"] = side
        notional = tick["p"] * tick["s"]

        self._expire(sym)
        w = self._windows[sym]
        w.ticks.append(tick)
        if side == "buy":
            w.buy_notional += notional
        else:
            w.sell_notional += notional

        for direction, total in [("buy", w.buy_notional), ("sell", w.sell_notional)]:
            if total >= self._alert:
                level = "whale" if total >= self._whale else "alert"
                self._pending_alerts.append({
                    "symbol": sym, "side": direction,
                    "notional": total, "level": level,
                    "timestamp": tick["t"],
                })
                # Reset window after trigger to avoid repeated alerts
                if direction == "buy":
                    w.buy_notional = 0.0
                else:
                    w.sell_notional = 0.0
                w.ticks = [t for t in w.ticks if t["_side"] != direction]

    def flush_alerts(self) -> list[dict]:
        alerts, self._pending_alerts = self._pending_alerts, []
        return alerts
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_block_detector.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/block_detector.py tests/test_block_detector.py
git commit -m "feat: add block detector with 30s sliding window and tick rule"
```

---

## Task 6: Chip Profile — VPOC / VAH / VAL

**Files:**
- Create: `backend/analysis/chip_profile.py` (partial — this task covers VPOC/VAH/VAL only)
- Create: `tests/test_chip_profile.py`

Domain note: Volume Profile groups all volume by price. VPOC = price bucket with most volume. Value Area = the range containing 70% of total volume, expanded bidirectionally from VPOC (always add the bucket — above or below — with more volume next).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_chip_profile.py
import pytest
from backend.analysis.chip_profile import ChipProfile

def test_vpoc_finds_highest_volume_bucket():
    cp = ChipProfile(bucket_size=0.10)
    # Two price levels, 580.00 has more volume
    cp.add_bar({"c": 580.0, "v": 1_000_000, "l": 579.5, "h": 580.5})
    cp.add_bar({"c": 575.0, "v": 500_000, "l": 574.5, "h": 575.5})
    result = cp.compute()
    assert result["vpoc"] == pytest.approx(580.0, abs=0.10)

def test_value_area_covers_70_percent():
    cp = ChipProfile(bucket_size=0.10)
    # Uniform volume across 10 buckets: VA must contain at least 7
    for i in range(10):
        cp.add_bar({"c": 580.0 + i * 0.10, "v": 100_000, "l": 580.0 + i * 0.10 - 0.05, "h": 580.0 + i * 0.10 + 0.05})
    result = cp.compute()
    total_vol = 1_000_000
    va_vol = sum(
        v for price, v in cp._buckets.items()
        if result["val"] <= price <= result["vah"]
    )
    assert va_vol / total_vol >= 0.70

def test_vpoc_bias_above_vpoc():
    cp = ChipProfile(bucket_size=0.10)
    cp.add_bar({"c": 580.0, "v": 1_000_000, "l": 579.5, "h": 580.5})
    cp._spot = 582.0
    result = cp.compute()
    assert result["vpoc_bias"] == "bullish"

def test_vpoc_bias_below_vpoc():
    cp = ChipProfile(bucket_size=0.10)
    cp.add_bar({"c": 580.0, "v": 1_000_000, "l": 579.5, "h": 580.5})
    cp._spot = 578.0
    result = cp.compute()
    assert result["vpoc_bias"] == "bearish"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_chip_profile.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement VPOC/VAH/VAL in chip_profile.py**

```python
from collections import defaultdict

BUCKET = 0.10  # $0.10 fixed bucket size

class ChipProfile:
    def __init__(self, bucket_size: float = BUCKET):
        self._bucket = bucket_size
        self._buckets: dict[float, float] = defaultdict(float)
        self._spot: float | None = None

    def _round_bucket(self, price: float) -> float:
        return round(round(price / self._bucket) * self._bucket, 2)

    def add_bar(self, bar: dict) -> None:
        """Distribute bar volume evenly across its price range buckets."""
        low = self._round_bucket(bar["l"])
        high = self._round_bucket(bar["h"])
        price = low
        buckets_in_range = []
        while price <= high + 1e-9:
            buckets_in_range.append(self._round_bucket(price))
            price = round(price + self._bucket, 2)
        if not buckets_in_range:
            buckets_in_range = [self._round_bucket(bar["c"])]
        vol_per_bucket = bar["v"] / len(buckets_in_range)
        for b in buckets_in_range:
            self._buckets[b] += vol_per_bucket

    def add_tick(self, price: float, size: float) -> None:
        """Add a single tick's volume to the profile."""
        self._buckets[self._round_bucket(price)] += size

    def set_spot(self, price: float) -> None:
        self._spot = price

    def compute(self) -> dict:
        if not self._buckets:
            return {"vpoc": 0, "vah": 0, "val": 0, "vpoc_bias": "neutral"}

        total_vol = sum(self._buckets.values())
        target = total_vol * 0.70

        # VPOC: bucket with max volume
        vpoc = max(self._buckets, key=self._buckets.__getitem__)

        # Value Area: bidirectional expansion from VPOC
        sorted_prices = sorted(self._buckets.keys())
        va_set = {vpoc}
        va_vol = self._buckets[vpoc]

        prices_above = [p for p in sorted_prices if p > vpoc]
        prices_below = [p for p in reversed(sorted_prices) if p < vpoc]
        idx_above = idx_below = 0

        while va_vol < target:
            vol_above = self._buckets[prices_above[idx_above]] if idx_above < len(prices_above) else 0
            vol_below = self._buckets[prices_below[idx_below]] if idx_below < len(prices_below) else 0
            if vol_above == 0 and vol_below == 0:
                break
            if vol_above >= vol_below and idx_above < len(prices_above):
                va_set.add(prices_above[idx_above])
                va_vol += vol_above
                idx_above += 1
            elif idx_below < len(prices_below):
                va_set.add(prices_below[idx_below])
                va_vol += vol_below
                idx_below += 1

        vah = max(va_set)
        val = min(va_set)

        spot = self._spot or vpoc
        bias = "bullish" if spot > vpoc else "bearish" if spot < vpoc else "neutral"

        return {"vpoc": vpoc, "vah": vah, "val": val, "vpoc_bias": bias}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_chip_profile.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/chip_profile.py tests/test_chip_profile.py
git commit -m "feat: add VPOC/VAH/VAL chip profile with $0.10 buckets"
```

---

## Task 7: Chip Profile — GEX / Max Pain

**Files:**
- Modify: `backend/analysis/chip_profile.py`
- Modify: `tests/test_chip_profile.py`

Domain note: GEX (Gamma Exposure) = sum of (Gamma × OI × 100 × spot) for each option contract, with calls positive and puts negative. When net GEX > 0, market makers are long gamma and will hedge by selling rallies / buying dips (mean-reversion). When GEX < 0, they amplify moves. Max Pain = the strike price where total value of expiring options is minimized for option buyers.

- [ ] **Step 1: Write failing tests**

```python
# Append to tests/test_chip_profile.py
def test_gex_positive_for_heavy_call_oi():
    cp = ChipProfile()
    cp._spot = 580.0
    options = [
        {"details": {"contract_type": "call", "strike_price": 580, "expiration_date": "2026-09-20"},
         "greeks": {"gamma": 0.05}, "open_interest": 10000, "day": {"volume": 500}},
        {"details": {"contract_type": "put", "strike_price": 575, "expiration_date": "2026-09-20"},
         "greeks": {"gamma": 0.03}, "open_interest": 2000, "day": {"volume": 200}},
    ]
    result = cp.compute_gex(options, spot=580.0)
    # Call GEX = 0.05 × 10000 × 100 × 580 = 29,000,000
    # Put GEX  = 0.03 × 2000 × 100 × 580 = 3,480,000 (negative)
    assert result["gex_net"] > 0
    assert result["gex_signal"] == "mean_revert"

def test_gex_neutral_when_below_threshold():
    cp = ChipProfile()
    options = [
        {"details": {"contract_type": "call", "strike_price": 580, "expiration_date": "2026-09-20"},
         "greeks": {"gamma": 0.0001}, "open_interest": 100, "day": {"volume": 10}},
    ]
    result = cp.compute_gex(options, spot=580.0)
    assert result["gex_signal"] == "neutral"

def test_max_pain_minimizes_buyer_value():
    cp = ChipProfile()
    options = [
        {"details": {"contract_type": "call", "strike_price": 580, "expiration_date": "2026-09-20"},
         "greeks": {"gamma": 0.05}, "open_interest": 5000, "day": {"volume": 100}},
        {"details": {"contract_type": "put", "strike_price": 575, "expiration_date": "2026-09-20"},
         "greeks": {"gamma": 0.04}, "open_interest": 8000, "day": {"volume": 100}},
    ]
    result = cp.compute_gex(options, spot=578.0)
    assert "max_pain" in result
    assert isinstance(result["max_pain"], float)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_chip_profile.py::test_gex_positive_for_heavy_call_oi -v
```
Expected: `AttributeError: 'ChipProfile' object has no attribute 'compute_gex'`

- [ ] **Step 3: Add compute_gex to chip_profile.py**

Add this method to the `ChipProfile` class:

```python
GEX_NEUTRAL_THRESHOLD = 500_000_000

def compute_gex(self, options: list[dict], spot: float) -> dict:
    """
    GEX = Gamma × OI × 100 × spot_price
    Calls contribute positive GEX, puts negative.
    """
    gex_by_strike: dict[float, float] = defaultdict(float)
    gex_net = 0.0

    for opt in options:
        greeks = opt.get("greeks") or {}
        gamma = greeks.get("gamma")
        if gamma is None:
            continue
        oi = opt.get("open_interest", 0) or 0
        contract_type = opt["details"]["contract_type"]
        strike = opt["details"]["strike_price"]
        sign = 1 if contract_type == "call" else -1
        gex = sign * gamma * oi * 100 * spot
        gex_net += gex
        gex_by_strike[strike] += gex

    if abs(gex_net) < GEX_NEUTRAL_THRESHOLD:
        gex_signal = "neutral"
    elif gex_net > 0:
        gex_signal = "mean_revert"
    else:
        gex_signal = "trend_amplify"

    # Max Pain: strike that minimizes total option buyer value
    strikes = sorted({opt["details"]["strike_price"] for opt in options})
    min_pain = float("inf")
    max_pain_strike = strikes[0] if strikes else spot

    for test_strike in strikes:
        pain = 0.0
        for opt in options:
            oi = opt.get("open_interest", 0) or 0
            k = opt["details"]["strike_price"]
            ct = opt["details"]["contract_type"]
            if ct == "call":
                pain += max(0, test_strike - k) * oi * 100
            else:
                pain += max(0, k - test_strike) * oi * 100
        if pain < min_pain:
            min_pain = pain
            max_pain_strike = test_strike

    gex_levels = [{"price": k, "gex": v} for k, v in sorted(gex_by_strike.items())]

    return {
        "gex_net": gex_net,
        "gex_signal": gex_signal,
        "max_pain": float(max_pain_strike),
        "gex_levels": gex_levels,
    }
```

- [ ] **Step 4: Run all chip profile tests**

```bash
pytest tests/test_chip_profile.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/chip_profile.py tests/test_chip_profile.py
git commit -m "feat: add GEX and Max Pain computation to chip profile"
```

---

## Task 8: Options Flow Scanner

**Files:**
- Create: `backend/analysis/options_flow.py`
- Create: `tests/test_options_flow.py`

Domain note: A "Sweep" = a large aggressive market order that sweeps multiple exchanges simultaneously (indicator of urgency). A "Block" = a single large negotiated trade on one exchange. In Polygon data, `conditions` code 71 = multi-exchange sweep. OTM % = how far the strike is from spot price.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_options_flow.py
import pytest
from backend.analysis.options_flow import OptionsFlowScanner

def make_option(contract_type, strike, premium, oi, iv, conditions=None):
    return {
        "details": {
            "contract_type": contract_type,
            "strike_price": strike,
            "expiration_date": "2026-09-20",
            "ticker": f"O:SPY260920C{int(strike*1000):08d}",
        },
        "greeks": {"delta": 0.6, "gamma": 0.05, "theta": -0.3, "vega": 0.2},
        "implied_volatility": iv,
        "open_interest": oi,
        "day": {"volume": int(premium / (strike * 0.1)), "vwap": strike * 0.1},
        "last_trade": {"price": premium / max(1, int(premium / (strike * 0.1))), "size": max(1, int(premium / (strike * 0.1))), "conditions": conditions or []},
    }

def test_identifies_whale_option():
    scanner = OptionsFlowScanner(alert_threshold=500_000, whale_threshold=1_000_000)
    option = make_option("call", 590, 1_200_000, 5000, 0.18)
    alerts = scanner.scan([option], spot=583.0)
    whale_alerts = [a for a in alerts if a["level"] == "whale"]
    assert len(whale_alerts) == 1
    assert whale_alerts[0]["premium"] >= 1_000_000

def test_marks_otm_correctly():
    scanner = OptionsFlowScanner(alert_threshold=500_000, whale_threshold=1_000_000)
    option = make_option("call", 600, 800_000, 5000, 0.22)  # 600 call, spot 583 → OTM
    alerts = scanner.scan([option], spot=583.0)
    assert alerts[0]["otm_pct"] > 0
    assert alerts[0]["otm_pct"] == pytest.approx((600 - 583) / 583 * 100, rel=0.01)

def test_ignores_small_premium():
    scanner = OptionsFlowScanner(alert_threshold=500_000, whale_threshold=1_000_000)
    option = make_option("call", 585, 100_000, 500, 0.15)
    alerts = scanner.scan([option], spot=583.0)
    assert len(alerts) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_options_flow.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement options_flow.py**

```python
SWEEP_CONDITIONS = {71}  # Polygon multi-exchange sweep condition

class OptionsFlowScanner:
    def __init__(self, alert_threshold: float, whale_threshold: float):
        self._alert = alert_threshold
        self._whale = whale_threshold

    def _estimate_premium(self, opt: dict) -> float:
        last = opt.get("last_trade") or {}
        price = last.get("price", 0) or 0
        size = last.get("size", 0) or 0
        return price * size * 100  # 1 contract = 100 shares

    def _flow_type(self, opt: dict) -> str:
        conditions = set((opt.get("last_trade") or {}).get("conditions", []) or [])
        return "sweep" if conditions & SWEEP_CONDITIONS else "block"

    def scan(self, options: list[dict], spot: float) -> list[dict]:
        alerts = []
        for opt in options:
            premium = self._estimate_premium(opt)
            if premium < self._alert:
                continue

            details = opt["details"]
            contract_type = details["contract_type"]
            strike = details["strike_price"]

            if contract_type == "call":
                otm_pct = max(0.0, (strike - spot) / spot * 100)
            else:
                otm_pct = max(0.0, (spot - strike) / spot * 100)

            level = "whale" if premium >= self._whale else "alert"
            alerts.append({
                "symbol": details["ticker"].split(":")[1][:3],
                "expiry": details["expiration_date"],
                "strike": strike,
                "contract_type": contract_type,
                "premium": premium,
                "flow_type": self._flow_type(opt),
                "iv": opt.get("implied_volatility", 0),
                "otm_pct": round(otm_pct, 2),
                "level": level,
            })
        return sorted(alerts, key=lambda x: x["premium"], reverse=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_options_flow.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/options_flow.py tests/test_options_flow.py
git commit -m "feat: add options flow scanner with Sweep/Block detection"
```

---

## Task 9: Sentiment — PCR + Reddit + News

**Files:**
- Create: `backend/analysis/sentiment.py`
- Create: `tests/test_sentiment.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sentiment.py
import pytest
from backend.analysis.sentiment import SentimentAnalyzer

def make_option_snap(contract_type, oi, volume):
    return {
        "details": {"contract_type": contract_type},
        "open_interest": oi,
        "day": {"volume": volume},
    }

def test_oi_pcr_bearish_signal():
    analyzer = SentimentAnalyzer()
    options = [
        make_option_snap("put", 15000, 500),
        make_option_snap("call", 10000, 800),
    ]
    result = analyzer.compute_pcr(options)
    assert result["oi_pcr"] == pytest.approx(1.5, rel=0.01)
    assert result["oi_pcr_signal"] == "bearish"

def test_volume_pcr_bullish_signal():
    analyzer = SentimentAnalyzer()
    options = [
        make_option_snap("put", 10000, 400),
        make_option_snap("call", 8000, 600),
    ]
    result = analyzer.compute_pcr(options)
    assert result["vol_pcr"] == pytest.approx(400/600, rel=0.01)
    assert result["vol_pcr_signal"] == "bullish"

def test_vader_scores_positive_text():
    analyzer = SentimentAnalyzer()
    score = analyzer._vader_score("SPY to the moon, very bullish today!")
    assert score > 0

def test_vader_scores_negative_text():
    analyzer = SentimentAnalyzer()
    score = analyzer._vader_score("Market crash incoming, very bearish, sell everything")
    assert score < 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sentiment.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement sentiment.py**

```python
import re
import logging
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    # OI PCR thresholds (slow/cumulative signal)
    OI_BULL = 0.7
    OI_BEAR = 1.3
    # Volume PCR thresholds (fast/intraday signal)
    VOL_BULL = 0.8
    VOL_BEAR = 1.2

    def __init__(self):
        self._vader = SentimentIntensityAnalyzer()

    def _vader_score(self, text: str) -> float:
        return self._vader.polarity_scores(text)["compound"]

    def compute_pcr(self, options: list[dict]) -> dict:
        put_oi = call_oi = put_vol = call_vol = 0
        for opt in options:
            ct = opt["details"]["contract_type"]
            oi = opt.get("open_interest", 0) or 0
            vol = (opt.get("day") or {}).get("volume", 0) or 0
            if ct == "put":
                put_oi += oi
                put_vol += vol
            else:
                call_oi += oi
                call_vol += vol

        oi_pcr = round(put_oi / call_oi, 3) if call_oi else 0
        vol_pcr = round(put_vol / call_vol, 3) if call_vol else 0

        oi_signal = "bullish" if oi_pcr < self.OI_BULL else "bearish" if oi_pcr > self.OI_BEAR else "neutral"
        vol_signal = "bullish" if vol_pcr < self.VOL_BULL else "bearish" if vol_pcr > self.VOL_BEAR else "neutral"

        return {
            "oi_pcr": oi_pcr, "oi_pcr_signal": oi_signal,
            "vol_pcr": vol_pcr, "vol_pcr_signal": vol_signal,
        }

    def score_reddit_posts(self, posts: list[dict]) -> float:
        """Returns aggregate bullish % from 0.0 to 1.0."""
        if not posts:
            return 0.5
        scores = [self._vader_score(p.get("title", "") + " " + p.get("selftext", "")) for p in posts]
        positive = sum(1 for s in scores if s > 0.05)
        return round(positive / len(scores), 3)

    def score_headlines(self, articles: list[dict]) -> float:
        if not articles:
            return 0.5
        scores = [self._vader_score(a.get("title", "")) for a in articles]
        positive = sum(1 for s in scores if s > 0.05)
        return round(positive / len(scores), 3)

    async def fetch_reddit(self, reddit_client, subreddits: list[str] = None, limit: int = 25) -> list[dict]:
        """Fetch hot posts from subreddits. Returns list of {title, selftext}."""
        subreddits = subreddits or ["wallstreetbets", "stocks"]
        posts = []
        try:
            for sub in subreddits:
                subreddit = await reddit_client.subreddit(sub)
                async for post in subreddit.hot(limit=limit):
                    posts.append({"title": post.title, "selftext": post.selftext[:500]})
        except Exception as e:
            logger.warning(f"Reddit fetch failed: {e}")
        return posts
```

Note: `vaderSentiment` must be added to requirements.txt:
```
vaderSentiment==3.3.2
asyncpraw==7.7.1
```
Then run `pip install vaderSentiment asyncpraw`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pip install vaderSentiment
pytest tests/test_sentiment.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/sentiment.py tests/test_sentiment.py requirements.txt
git commit -m "feat: add sentiment analyzer with dual PCR and VADER scoring"
```

---

## Task 10: Redis Cache (Atomic Writes)

**Files:**
- Create: `backend/cache/redis_cache.py`
- Create: `tests/test_redis_cache.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_redis_cache.py
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from backend.cache.redis_cache import RedisCache

@pytest.mark.asyncio
async def test_write_uses_atomic_rename():
    cache = RedisCache(url="redis://localhost:6379", ttl=600)
    mock_redis = AsyncMock()
    cache._redis = mock_redis

    await cache.write_snapshot("SPY", {"vpoc": 580.0, "spot": 583.0})

    # Should write to tmp key first, then rename
    calls = mock_redis.set.call_args_list
    assert any("tmp" in str(c) for c in calls), "Expected tmp key write"
    mock_redis.rename.assert_called_once()

@pytest.mark.asyncio
async def test_read_returns_parsed_snapshot():
    cache = RedisCache(url="redis://localhost:6379", ttl=600)
    payload = {"vpoc": 580.0, "written_at": "2026-09-14T09:15:00"}
    mock_redis = AsyncMock()
    mock_redis.get.return_value = json.dumps(payload)
    cache._redis = mock_redis

    result = await cache.read_snapshot("SPY")
    assert result["vpoc"] == 580.0
    assert result["written_at"] == "2026-09-14T09:15:00"

@pytest.mark.asyncio
async def test_read_returns_none_when_missing():
    cache = RedisCache(url="redis://localhost:6379", ttl=600)
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    cache._redis = mock_redis

    result = await cache.read_snapshot("SPY")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_redis_cache.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement redis_cache.py**

```python
import json
import logging
from datetime import datetime, timezone
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self, url: str, ttl: int = 600):
        self._url = url
        self._ttl = ttl
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._redis = aioredis.from_url(self._url, decode_responses=True)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()

    async def write_snapshot(self, symbol: str, data: dict) -> None:
        """Atomic write: set tmp key → RENAME to latest, preventing dirty reads."""
        data["written_at"] = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(data)
        tmp_key = f"snapshot:{symbol}:tmp"
        final_key = f"snapshot:{symbol}:latest"
        try:
            await self._redis.set(tmp_key, payload, ex=self._ttl)
            await self._redis.rename(tmp_key, final_key)
            await self._redis.expire(final_key, self._ttl)
        except Exception as e:
            logger.error(f"Redis write failed for {symbol}: {e}")

    async def read_snapshot(self, symbol: str) -> dict | None:
        try:
            raw = await self._redis.get(f"snapshot:{symbol}:latest")
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.error(f"Redis read failed for {symbol}: {e}")
            return None

    async def read_latest_or_stale(self, symbol: str) -> dict | None:
        """Returns latest if available, else None (frontend handles stale display)."""
        return await self.read_snapshot(symbol)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_redis_cache.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/cache/redis_cache.py tests/test_redis_cache.py
git commit -m "feat: add Redis cache with atomic tmp→RENAME snapshot writes"
```

---

## Task 11: Dual Worker Call Queue

**Files:**
- Create: `backend/ai/call_queue.py`
- Create: `tests/test_call_queue.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_call_queue.py
import pytest
import asyncio
from unittest.mock import AsyncMock
from backend.ai.call_queue import CallQueue

@pytest.mark.asyncio
async def test_whale_tasks_execute_before_regular():
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

    # Both should execute (different workers)
    assert "whale" in executed
    assert "regular" in executed

@pytest.mark.asyncio
async def test_drops_low_priority_when_full():
    calls = []
    async def slow_handler(task):
        calls.append(task["type"])
        await asyncio.sleep(0.05)

    q = CallQueue(handler=slow_handler, maxsize=2)
    await q.start()

    # Fill regular queue
    for i in range(5):
        await q.enqueue({"priority": "regular", "type": f"hourly_{i}"})

    await asyncio.sleep(0.5)
    await q.stop()
    # maxsize=2: only 2 regular tasks should have been accepted
    regular = [c for c in calls if "hourly" in c]
    assert len(regular) <= 3  # queue of 2 + 1 being processed
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_call_queue.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement call_queue.py**

```python
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
        self._tasks: list[asyncio.Task] = []

    async def enqueue(self, task: dict) -> bool:
        """Returns True if enqueued, False if dropped."""
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
        self._tasks = [
            asyncio.create_task(self._worker(self._whale_q, "whale")),
            asyncio.create_task(self._worker(self._regular_q, "regular")),
        ]

    async def stop(self) -> None:
        await self._whale_q.put(None)
        await self._regular_q.put(None)
        await asyncio.gather(*self._tasks, return_exceptions=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_call_queue.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/ai/call_queue.py tests/test_call_queue.py
git commit -m "feat: add dual-worker async call queue for Claude API"
```

---

## Task 12: Claude Interpreter

**Files:**
- Create: `backend/ai/interpreter.py`
- Create: `tests/test_interpreter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_interpreter.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from backend.ai.interpreter import Interpreter

@pytest.mark.asyncio
async def test_returns_structured_output():
    interp = Interpreter(api_key="test_key")
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "support": 576, "resistance": 588, "bias": "bullish",
        "key_level": 583, "trigger_long": "hold 578 VPOC",
        "trigger_short": "break 578", "confidence": "medium",
        "summary": "Large call sweep + GEX mean-revert favors upside."
    }))]

    with patch.object(interp._client.messages, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await interp.interpret({
            "spy_spot": 583.4, "vpoc": 578, "vah": 585, "val": 574,
            "gex_signal": "mean_revert", "oi_pcr": 0.9, "vol_pcr": 0.85,
            "vix": 18.2, "vvix_ratio": 1.1, "bias": "bullish",
            "top_headlines": [], "options_alerts": [],
        })

    assert result["support"] == 576
    assert result["resistance"] == 588
    assert result["confidence"] == "medium"

@pytest.mark.asyncio
async def test_handles_invalid_json_gracefully():
    interp = Interpreter(api_key="test_key")
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="not valid json")]

    with patch.object(interp._client.messages, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await interp.interpret({"spy_spot": 580})

    assert result["bias"] == "unknown"
    assert "error" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_interpreter.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement interpreter.py**

```python
import json
import logging
import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a professional U.S. equity market analyst specializing in SPY and QQQ intraday flow analysis. Your job is to interpret real-time market microstructure data and provide actionable intraday price range predictions.

Always respond with a single JSON object. No markdown, no explanation outside the JSON. The JSON must contain exactly these keys: support (float), resistance (float), bias (string: bullish/bearish/neutral), key_level (float), trigger_long (string), trigger_short (string), confidence (string: high/medium/low), summary (string, max 100 Chinese characters)."""

class Interpreter:
    def __init__(self, api_key: str):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def interpret(self, data: dict) -> dict:
        user_content = self._build_prompt(data)
        try:
            response = await self._client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                system=anthropic.NOT_GIVEN,
                messages=[{"role": "user", "content": user_content}],
                # system prompt caching
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            )
            raw = response.content[0].text.strip()
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Claude returned invalid JSON: {e}")
            return {"bias": "unknown", "error": str(e), "summary": "解读失败"}
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return {"bias": "unknown", "error": str(e), "summary": "API 错误"}

    def _build_prompt(self, d: dict) -> str:
        lines = [
            f"分析时间: {d.get('timestamp', 'N/A')}",
            f"SPY: {d.get('spy_spot')} | QQQ: {d.get('qqq_spot', 'N/A')}",
            f"大单净流: SPY {d.get('spy_net_flow', 0):+.0f} | QQQ {d.get('qqq_net_flow', 0):+.0f}",
            f"VPOC: {d.get('vpoc')} | VAH: {d.get('vah')} | VAL: {d.get('val')}",
            f"GEX信号: {d.get('gex_signal')} | GEX净值: {d.get('gex_net', 0):.0f}",
            f"OI PCR: {d.get('oi_pcr')} ({d.get('oi_pcr_signal')}) | Volume PCR: {d.get('vol_pcr')} ({d.get('vol_pcr_signal')})",
            f"VIX: {d.get('vix')} | VVIX/VIX: {d.get('vvix_ratio', 'N/A')} (>1.2=短期恐慌脉冲)",
        ]
        if d.get("es_nq_trend"):
            lines.append(f"ES/NQ隔夜走势: {d['es_nq_trend']}")
        if d.get("economic_events"):
            lines.append(f"今日经济日历: {d['economic_events']}")
        if d.get("options_alerts"):
            lines.append(f"期权异动(前3): {json.dumps(d['options_alerts'][:3], ensure_ascii=False)}")
        if d.get("top_headlines"):
            lines.append(f"新闻摘要: {' | '.join(d['top_headlines'][:3])}")

        lines.append("\n请输出JSON格式的分析结果，包含今日支撑位、压力位、方向偏向、关键触发价位。")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_interpreter.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/ai/interpreter.py tests/test_interpreter.py
git commit -m "feat: add Claude interpreter with prompt caching and structured output"
```

---

## Task 13: Discord Notifier

**Files:**
- Create: `backend/notifier/discord.py`
- Create: `tests/test_discord.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_discord.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.notifier.discord import DiscordNotifier

@pytest.mark.asyncio
async def test_sends_whale_embed():
    notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
    alert = {"symbol": "SPY", "side": "buy", "notional": 55_000_000, "level": "whale", "timestamp": 1700000000000}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 204
        await notifier.send_block_alert(alert)

    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert len(payload["embeds"]) == 1
    assert "SPY" in payload["embeds"][0]["title"]

@pytest.mark.asyncio
async def test_respects_cooldown():
    import time
    notifier = DiscordNotifier(webhook_url="https://discord.com/test", cooldown_seconds=300)
    notifier._last_sent["SPY"] = time.time()  # just sent

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        await notifier.send_block_alert({"symbol": "SPY", "side": "buy", "notional": 60_000_000, "level": "whale", "timestamp": 0})

    mock_post.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_discord.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement discord.py**

```python
import time
import logging
import httpx
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

COLOR_BULL = 0x22C55E
COLOR_BEAR = 0xEF4444
COLOR_INFO = 0x38BDF8
COLOR_WARN = 0xFFA657

class DiscordNotifier:
    def __init__(self, webhook_url: str, cooldown_seconds: int = 300):
        self._url = webhook_url
        self._cooldown = cooldown_seconds
        self._last_sent: dict[str, float] = {}

    def _can_send(self, key: str) -> bool:
        last = self._last_sent.get(key, 0)
        return time.time() - last > self._cooldown

    async def _post(self, payload: dict) -> None:
        async with httpx.AsyncClient() as client:
            r = await client.post(self._url, json=payload)
            r.raise_for_status()

    async def send_block_alert(self, alert: dict) -> None:
        sym = alert["symbol"]
        key = f"block:{sym}"
        if not self._can_send(key):
            return
        color = COLOR_BULL if alert["side"] == "buy" else COLOR_BEAR
        direction = "买入" if alert["side"] == "buy" else "卖出"
        embed = {
            "title": f"⚡ 大单异动 — {sym}",
            "color": color,
            "fields": [
                {"name": "方向", "value": direction, "inline": True},
                {"name": "金额", "value": f"${alert['notional']/1e6:.1f}M", "inline": True},
                {"name": "级别", "value": "🐋 Whale" if alert["level"] == "whale" else "🔔 Alert", "inline": True},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._post({"embeds": [embed]})
        self._last_sent[key] = time.time()

    async def send_options_alert(self, alert: dict) -> None:
        sym = alert["symbol"]
        key = f"options:{sym}:{alert['strike']}:{alert['contract_type']}"
        if not self._can_send(key):
            return
        color = COLOR_BULL if alert["contract_type"] == "call" else COLOR_BEAR
        embed = {
            "title": f"⚡ 期权异动 — {sym}",
            "color": color,
            "fields": [
                {"name": "合约", "value": f"{alert['strike']}{alert['contract_type'].upper()[0]} {alert['expiry']}", "inline": True},
                {"name": "权利金", "value": f"${alert['premium']/1e6:.2f}M", "inline": True},
                {"name": "类型", "value": alert["flow_type"].upper(), "inline": True},
                {"name": "IV", "value": f"{alert['iv']*100:.1f}%", "inline": True},
                {"name": "OTM", "value": f"{alert['otm_pct']:.1f}%", "inline": True},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._post({"embeds": [embed]})
        self._last_sent[key] = time.time()

    async def send_premarket_report(self, interpretation: dict, pcr: dict, vix: float, events: list[str]) -> None:
        embed = {
            "title": "📋 早盘报告",
            "color": COLOR_BULL if interpretation.get("bias") == "bullish" else COLOR_BEAR if interpretation.get("bias") == "bearish" else COLOR_INFO,
            "fields": [
                {"name": "支撑 / 压力", "value": f"{interpretation.get('support')} / {interpretation.get('resistance')}", "inline": True},
                {"name": "方向", "value": interpretation.get("bias", "N/A"), "inline": True},
                {"name": "置信度", "value": interpretation.get("confidence", "N/A"), "inline": True},
                {"name": "多头触发", "value": interpretation.get("trigger_long", "N/A"), "inline": False},
                {"name": "空头触发", "value": interpretation.get("trigger_short", "N/A"), "inline": False},
                {"name": "VIX", "value": str(vix), "inline": True},
                {"name": "OI PCR", "value": f"{pcr.get('oi_pcr')} ({pcr.get('oi_pcr_signal')})", "inline": True},
                {"name": "今日经济日历", "value": "\n".join(events) if events else "无重要事件", "inline": False},
                {"name": "AI摘要", "value": interpretation.get("summary", ""), "inline": False},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._post({"embeds": [embed]})

    async def send_hourly_brief(self, symbol: str, snapshot: dict) -> None:
        interp = snapshot.get("interpretation", {})
        embed = {
            "title": f"📊 每小时简报 — {symbol}",
            "color": COLOR_INFO,
            "fields": [
                {"name": "现价", "value": str(snapshot.get("spot")), "inline": True},
                {"name": "VPOC", "value": str(snapshot.get("vpoc")), "inline": True},
                {"name": "GEX", "value": snapshot.get("gex_signal", "N/A"), "inline": True},
                {"name": "VIX", "value": str(snapshot.get("vix", "N/A")), "inline": True},
                {"name": "Vol PCR", "value": f"{snapshot.get('vol_pcr')} ({snapshot.get('vol_pcr_signal')})", "inline": True},
                {"name": "AI简报", "value": interp.get("summary", "N/A"), "inline": False},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._post({"embeds": [embed]})

    async def send_closing_summary(self, snapshots: dict, interpretation: dict) -> None:
        embed = {
            "title": "📋 收盘总结",
            "color": COLOR_INFO,
            "fields": [
                {"name": "AI收盘摘要", "value": interpretation.get("summary", "N/A"), "inline": False},
                {"name": "预测准确度", "value": interpretation.get("accuracy_note", "待人工评估"), "inline": False},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._post({"embeds": [embed]})
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_discord.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/notifier/discord.py tests/test_discord.py
git commit -m "feat: add Discord notifier with 4 message types and cooldown"
```

---

## Task 14: Scheduler

**Files:**
- Create: `backend/scheduler.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_scheduler.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.scheduler import MarketScheduler

@pytest.mark.asyncio
async def test_registers_three_job_types():
    scheduler = MarketScheduler(
        premarket_handler=AsyncMock(),
        hourly_handler=AsyncMock(),
        close_handler=AsyncMock(),
    )
    scheduler.setup()
    jobs = scheduler._scheduler.get_jobs()
    job_ids = [j.id for j in jobs]
    assert "premarket" in job_ids
    assert "close" in job_ids
    assert any("hourly" in jid for jid in job_ids)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_scheduler.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement scheduler.py**

```python
import logging
from typing import Callable, Awaitable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

class MarketScheduler:
    def __init__(
        self,
        premarket_handler: Callable[[], Awaitable[None]],
        hourly_handler: Callable[[], Awaitable[None]],
        close_handler: Callable[[], Awaitable[None]],
        timezone: str = "America/New_York",
    ):
        self._premarket = premarket_handler
        self._hourly = hourly_handler
        self._close = close_handler
        self._tz = timezone
        self._scheduler = AsyncIOScheduler(timezone=timezone)

    def setup(self) -> None:
        # Pre-market: 9:15 ET, Mon-Fri
        self._scheduler.add_job(
            self._premarket, CronTrigger(hour=9, minute=15, day_of_week="mon-fri", timezone=self._tz),
            id="premarket", replace_existing=True,
        )
        # Hourly: 10:00–15:00 ET, Mon-Fri
        for hour in range(10, 16):
            self._scheduler.add_job(
                self._hourly, CronTrigger(hour=hour, minute=0, day_of_week="mon-fri", timezone=self._tz),
                id=f"hourly_{hour}", replace_existing=True,
            )
        # Close: 16:00 ET, Mon-Fri
        self._scheduler.add_job(
            self._close, CronTrigger(hour=16, minute=0, day_of_week="mon-fri", timezone=self._tz),
            id="close", replace_existing=True,
        )

    def start(self) -> None:
        self.setup()
        self._scheduler.start()
        logger.info("Scheduler started")

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_scheduler.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scheduler.py tests/test_scheduler.py
git commit -m "feat: add AsyncIOScheduler with pre-market, hourly, close jobs"
```

---

## Task 15: FastAPI App — Routes + CORS + Lifespan

**Files:**
- Create: `backend/api/routes.py`
- Create: `backend/main.py`
- Create: `tests/test_routes.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_routes.py
import pytest
import json
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_health_returns_ok():
    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_snapshot_returns_cached_data():
    from backend.main import app
    snapshot_data = {"spy": {"spot": 583.4, "vpoc": 578.0, "written_at": "2026-09-14T10:00:00+00:00"}}

    with patch("backend.api.routes.cache.read_snapshot", new_callable=AsyncMock, return_value=snapshot_data["spy"]):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/snapshot?symbol=SPY")

    assert r.status_code == 200
    data = r.json()
    assert "written_at" in data

@pytest.mark.asyncio
async def test_cors_headers_present():
    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.options("/api/health", headers={"Origin": "https://test.netlify.app", "Access-Control-Request-Method": "GET"})
    assert r.status_code in (200, 204)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_routes.py -v
```
Expected: `ImportError` or connection error

- [ ] **Step 3: Create routes.py**

```python
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from backend.cache.redis_cache import RedisCache

router = APIRouter()
cache: RedisCache = None  # injected at startup

@router.get("/api/health")
async def health():
    return {"status": "ok"}

@router.get("/api/snapshot")
async def snapshot(symbol: str = Query(default="SPY")):
    data = await cache.read_snapshot(symbol.upper())
    if data is None:
        return JSONResponse(status_code=503, content={"error": "no data available"})
    return data

@router.get("/api/snapshot/all")
async def snapshot_all():
    from backend.config import settings
    result = {}
    for sym in settings.symbols:
        result[sym.lower()] = await cache.read_snapshot(sym) or {}
    return result
```

- [ ] **Step 4: Create main.py**

```python
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.api import routes
from backend.cache.redis_cache import RedisCache
from backend.data.polygon_rest import PolygonREST
from backend.data.polygon_ws import PolygonWebSocket
from backend.analysis.block_detector import BlockDetector
from backend.analysis.chip_profile import ChipProfile
from backend.analysis.options_flow import OptionsFlowScanner
from backend.analysis.sentiment import SentimentAnalyzer
from backend.ai.call_queue import CallQueue
from backend.ai.interpreter import Interpreter
from backend.notifier.discord import DiscordNotifier
from backend.scheduler import MarketScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_cache = RedisCache(url=settings.redis_url, ttl=settings.snapshot_ttl_seconds)
_rest = PolygonREST(api_key=settings.polygon_api_key)
_block_det = {s: BlockDetector(settings.block_window_seconds, settings.stock_whale_threshold, settings.stock_alert_threshold) for s in settings.symbols}
_chip = {s: ChipProfile() for s in settings.symbols}
_options_scanner = OptionsFlowScanner(settings.options_alert_threshold, settings.options_whale_threshold)
_sentiment = SentimentAnalyzer()
_discord = DiscordNotifier(settings.discord_webhook_url, settings.discord_cooldown_seconds)
_interpreter = Interpreter(api_key=settings.anthropic_api_key)

async def _handle_ai_task(task: dict) -> None:
    interp = await _interpreter.interpret(task.get("data", {}))
    if task["type"] == "whale_block":
        pass  # Discord alert already sent by block detector handler
    elif task["type"] in ("hourly", "premarket", "close"):
        for sym in settings.symbols:
            snap = await _cache.read_snapshot(sym) or {}
            await _discord.send_hourly_brief(sym, {**snap, "interpretation": interp})

_call_queue = CallQueue(handler=_handle_ai_task)

def _on_tick(tick: dict) -> None:
    sym = tick.get("sym")
    if sym not in _block_det:
        return
    _block_det[sym].ingest(tick)
    _chip[sym].add_tick(tick["p"], tick["s"])
    alerts = _block_det[sym].flush_alerts()
    for alert in alerts:
        if alert["level"] == "whale":
            asyncio.create_task(_discord.send_block_alert(alert))
            asyncio.create_task(_call_queue.enqueue({"priority": "whale", "type": "whale_block", "data": alert}))

_ws = PolygonWebSocket(api_key=settings.polygon_api_key, symbols=settings.symbols)
_ws.on_tick = _on_tick

async def _premarket_job():
    logger.info("Running pre-market job")
    for sym in settings.symbols:
        bars = await _rest.get_daily_bars(sym, days=20)
        for bar in bars:
            _chip[sym].add_bar(bar)
        spot = await _rest.get_spot_price(sym)
        _chip[sym].set_spot(spot)
        options = await _rest.get_options_snapshot(sym)
        chip_result = _chip[sym].compute()
        gex_result = _chip[sym].compute_gex(options, spot)
        pcr = _sentiment.compute_pcr(options)
        news = await _rest.get_news(settings.symbols)
        snap = {**chip_result, **gex_result, **pcr, "spot": spot, "options_count": len(options)}
        await _cache.write_snapshot(sym, snap)
    await _call_queue.enqueue({"priority": "whale", "type": "premarket", "data": snap})

async def _hourly_job():
    await _call_queue.enqueue({"priority": "regular", "type": "hourly", "data": {}})

async def _close_job():
    await _call_queue.enqueue({"priority": "whale", "type": "close", "data": {}})

_scheduler = MarketScheduler(
    premarket_handler=_premarket_job,
    hourly_handler=_hourly_job,
    close_handler=_close_job,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await _cache.connect()
    await _call_queue.start()
    _scheduler.start()
    ws_task = asyncio.create_task(_ws.run())
    routes.cache = _cache
    logger.info("Market monitor started")
    yield
    ws_task.cancel()
    _scheduler.stop()
    await _call_queue.stop()
    await _cache.close()
    await _rest.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://*.netlify.app", "http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(routes.router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_routes.py -v
```
Expected: PASS

- [ ] **Step 6: Run all tests**

```bash
pytest tests/ -v
```
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add backend/api/routes.py backend/main.py tests/test_routes.py
git commit -m "feat: add FastAPI app with CORS, lifespan, routes, and scheduler wiring"
```

---

## Task 16: Railway Deployment

**Files:**
- Create: `railway.json`
- Create: `Procfile`
- Create: `.env` (local, not committed)

- [ ] **Step 1: Create railway.json**

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn backend.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/api/health",
    "healthcheckTimeout": 30,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

- [ ] **Step 2: Create Procfile (fallback)**

```
web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

- [ ] **Step 3: Verify app starts locally**

```bash
cp .env.example .env
# Fill in real API keys in .env
uvicorn backend.main:app --reload
```

Open http://localhost:8000/api/health — expected: `{"status":"ok"}`

- [ ] **Step 4: Deploy to Railway**

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
2. Add Redis plugin: `+ New` → `Redis` in the same project
3. Set environment variables from `.env` in Railway dashboard (Settings → Variables)
4. Set `REDIS_URL` to Railway's auto-provisioned Redis URL (available as `$REDIS_URL` variable)
5. Deploy — watch logs for `Market monitor started`

- [ ] **Step 5: Verify deployment**

```bash
curl https://your-app.railway.app/api/health
```
Expected: `{"status":"ok"}`

- [ ] **Step 6: Commit**

```bash
git add railway.json Procfile
git commit -m "chore: add Railway deployment config"
```

---

## Self-Review

**Spec coverage check:**

| Spec Requirement | Task |
|---|---|
| Polygon WebSocket T.* real-time tick | Task 4 + Task 15 |
| 30s sliding window block detection + aggressor side | Task 5 |
| VPOC/VAH/VAL $0.10 bucket bidirectional 70% | Task 6 |
| GEX = Gamma × OI × 100 × spot + neutral threshold | Task 7 |
| Options flow $500K/$1M, Sweep/Block, OTM | Task 8 |
| OI PCR + Volume PCR separate thresholds | Task 9 |
| Reddit VADER sentiment | Task 9 |
| Redis atomic tmp→RENAME + written_at | Task 10 |
| Dual worker queue Whale + regular | Task 11 |
| Claude interpreter structured JSON output | Task 12 |
| Discord 4 message types + 5min cooldown | Task 13 |
| AsyncIOScheduler 9:15/hourly/16:00 | Task 14 |
| FastAPI + CORS + /api/snapshot | Task 15 |
| Railway Hobby deployment | Task 16 |
| VIX/VVIX data | ⚠️ Not covered — see note below |

**VIX/VVIX gap:** The spec requires VIX/VVIX data from Polygon REST. Add a `get_spot_price("VIX")` and `get_spot_price("VVIX")` call in `_premarket_job` and the hourly update in `main.py`. The `PolygonREST.get_spot_price` method in Task 3 handles this — just call it with `"VIX"` and `"VVIX"` tickers and pass the values to the snapshot and interpreter.

**Options every 10 minutes in main.py:** The `_premarket_job` loads options once. For the intraday 10-minute refresh, add a job in `scheduler.py`:

```python
self._scheduler.add_job(
    options_refresh_handler,
    CronTrigger(minute="*/10", hour="9-16", day_of_week="mon-fri", timezone=self._tz),
    id="options_refresh", replace_existing=True,
)
```

Add `options_refresh_handler` parameter to `MarketScheduler.__init__` and wire it in `main.py` to re-fetch options and recompute GEX/PCR/flow.
