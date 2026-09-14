import time
from backend.analysis.block_detector import BlockDetector


def make_tick(sym, price, size, side="buy", ts_offset=0):
    return {
        "ev": "T", "sym": sym, "p": price, "s": size,
        "t": int((time.time() + ts_offset) * 1000),
        "_side": side,
    }


def test_aggregates_same_direction_within_window():
    det = BlockDetector(window_seconds=30, whale_threshold=50_000_000, alert_threshold=20_000_000)
    for i in range(3):
        det.ingest(make_tick("SPY", 500.0, 20_000, "buy", ts_offset=i * 0.001))
    alerts = det.flush_alerts()
    assert len(alerts) == 1
    assert alerts[0]["notional"] >= 20_000_000
    assert alerts[0]["side"] == "buy"


def test_does_not_aggregate_opposite_directions():
    det = BlockDetector(window_seconds=30, whale_threshold=50_000_000, alert_threshold=20_000_000)
    det.ingest(make_tick("SPY", 500.0, 20_000, "buy"))
    det.ingest(make_tick("SPY", 500.0, 20_000, "sell"))
    alerts = det.flush_alerts()
    assert len(alerts) == 0


def test_expires_old_ticks():
    det = BlockDetector(window_seconds=1, whale_threshold=50_000_000, alert_threshold=5_000_000)
    det.ingest(make_tick("SPY", 500.0, 5_000, "buy", ts_offset=-2))
    det.ingest(make_tick("SPY", 500.0, 5_000, "buy"))
    alerts = det.flush_alerts()
    assert len(alerts) == 0


def test_determines_side_from_tick_rule():
    det = BlockDetector(window_seconds=30, whale_threshold=50_000_000, alert_threshold=1_000)
    tick1 = {"ev": "T", "sym": "SPY", "p": 583.0, "s": 10, "t": int(time.time() * 1000)}
    tick2 = {"ev": "T", "sym": "SPY", "p": 584.0, "s": 10, "t": int(time.time() * 1000) + 100}
    det.ingest(tick1)
    det.ingest(tick2)
    assert det._last_price["SPY"] == 584.0


def test_whale_level_flagged():
    det = BlockDetector(window_seconds=30, whale_threshold=50_000_000, alert_threshold=20_000_000)
    det.ingest(make_tick("SPY", 500.0, 120_000, "buy"))
    alerts = det.flush_alerts()
    assert len(alerts) == 1
    assert alerts[0]["level"] == "whale"
