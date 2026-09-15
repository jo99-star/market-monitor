import pytest
from backend.analysis.options_flow import OptionsFlowScanner


def make_option(contract_type, strike, premium, oi, iv, conditions=None):
    # price_per_share × size × 100 = total premium
    price_per_share = max(0.01, strike * 0.1)
    size = max(1, int(premium / (price_per_share * 100)))
    return {
        "details": {
            "contract_type": contract_type,
            "strike_price": strike,
            "expiration_date": "2026-09-20",
            "ticker": f"O:SPY260920C{int(strike * 1000):08d}",
        },
        "greeks": {"delta": 0.6, "gamma": 0.05, "theta": -0.3, "vega": 0.2},
        "implied_volatility": iv,
        "open_interest": oi,
        "day": {"volume": size, "vwap": price_per_share},
        "last_trade": {
            "price": price_per_share,
            "size": size,
            "conditions": conditions or [],
        },
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
    option = make_option("call", 600, 800_000, 5000, 0.22)
    alerts = scanner.scan([option], spot=583.0)
    assert len(alerts) == 1
    assert alerts[0]["otm_pct"] > 0
    assert alerts[0]["otm_pct"] == pytest.approx((600 - 583) / 583 * 100, rel=0.01)


def test_ignores_small_premium():
    scanner = OptionsFlowScanner(alert_threshold=500_000, whale_threshold=1_000_000)
    option = make_option("call", 585, 100_000, 500, 0.15)
    alerts = scanner.scan([option], spot=583.0)
    assert len(alerts) == 0


def test_flow_type_defaults_to_block():
    """All options are classified as 'block'; Polygon has no reliable sweep condition code."""
    scanner = OptionsFlowScanner(alert_threshold=500_000, whale_threshold=1_000_000)
    option = make_option("call", 585, 600_000, 3000, 0.17, conditions=[71])
    alerts = scanner.scan([option], spot=583.0)
    assert len(alerts) == 1
    assert alerts[0]["flow_type"] == "block"


def test_sorted_by_premium_descending():
    scanner = OptionsFlowScanner(alert_threshold=500_000, whale_threshold=1_000_000)
    options = [
        make_option("call", 585, 600_000, 3000, 0.17),
        make_option("call", 590, 1_500_000, 5000, 0.18),
    ]
    alerts = scanner.scan(options, spot=583.0)
    assert alerts[0]["premium"] > alerts[1]["premium"]
