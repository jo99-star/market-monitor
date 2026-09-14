import time
from collections import defaultdict
from dataclasses import dataclass, field

BUY_CONDITIONS = {41}
SELL_CONDITIONS = {38}


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
                    "symbol": sym,
                    "side": direction,
                    "notional": total,
                    "level": level,
                    "timestamp": tick["t"],
                })
                if direction == "buy":
                    w.buy_notional = 0.0
                else:
                    w.sell_notional = 0.0
                w.ticks = [t for t in w.ticks if t["_side"] != direction]

    def flush_alerts(self) -> list[dict]:
        alerts, self._pending_alerts = self._pending_alerts, []
        return alerts
