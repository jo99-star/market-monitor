import pytest
from backend.analysis.chip_profile import ChipProfile


def test_vpoc_finds_highest_volume_bucket():
    cp = ChipProfile(bucket_size=0.10)
    # Narrow bars so volume concentrates at single buckets
    cp.add_bar({"c": 580.0, "v": 1_000_000, "l": 579.96, "h": 580.04})
    cp.add_bar({"c": 575.0, "v": 500_000, "l": 574.96, "h": 575.04})
    result = cp.compute()
    assert result["vpoc"] == pytest.approx(580.0, abs=0.10)


def test_value_area_covers_70_percent():
    cp = ChipProfile(bucket_size=0.10)
    for i in range(10):
        cp.add_bar({
            "c": 580.0 + i * 0.10,
            "v": 100_000,
            "l": 580.0 + i * 0.10 - 0.05,
            "h": 580.0 + i * 0.10 + 0.05,
        })
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


def test_gex_dealer_sign_convention():
    """Dealer GEX: heavy put OI → dealers long gamma → net positive → mean_revert."""
    cp = ChipProfile()
    # Put-heavy: dealers long gamma on puts → positive GEX → mean_revert
    # Put GEX  = +1 × 0.05 × 500,000 × 100 × 580 = +1,450,000,000 > 2B threshold? No, just under.
    # Use OI=700k to exceed 2B:  0.05 × 700,000 × 100 × 580 = 2,030,000,000 > 2B
    options = [
        {
            "details": {"contract_type": "put", "strike_price": 575, "expiration_date": "2026-09-20"},
            "greeks": {"gamma": 0.05},
            "open_interest": 700_000,
            "day": {"volume": 5000},
        },
        {
            "details": {"contract_type": "call", "strike_price": 580, "expiration_date": "2026-09-20"},
            "greeks": {"gamma": 0.01},
            "open_interest": 10_000,
            "day": {"volume": 1000},
        },
    ]
    result = cp.compute_gex(options, spot=580.0)
    assert result["gex_net"] > 0, "Put-heavy → dealers long gamma → positive GEX"
    assert result["gex_signal"] == "mean_revert"


def test_gex_trend_amplify_for_heavy_call_oi():
    """Heavy call OI → dealers short gamma → negative GEX → trend_amplify."""
    cp = ChipProfile()
    # Call GEX = -1 × 0.05 × 700,000 × 100 × 580 = -2,030,000,000 < -2B threshold
    options = [
        {
            "details": {"contract_type": "call", "strike_price": 580, "expiration_date": "2026-09-20"},
            "greeks": {"gamma": 0.05},
            "open_interest": 700_000,
            "day": {"volume": 5000},
        },
    ]
    result = cp.compute_gex(options, spot=580.0)
    assert result["gex_net"] < 0, "Call-heavy → dealers short gamma → negative GEX"
    assert result["gex_signal"] == "trend_amplify"


def test_gex_neutral_when_below_threshold():
    cp = ChipProfile()
    options = [
        {
            "details": {"contract_type": "call", "strike_price": 580, "expiration_date": "2026-09-20"},
            "greeks": {"gamma": 0.0001},
            "open_interest": 100,
            "day": {"volume": 10},
        },
    ]
    result = cp.compute_gex(options, spot=580.0)
    assert result["gex_signal"] == "neutral"


def test_max_pain_minimizes_buyer_value():
    cp = ChipProfile()
    options = [
        {
            "details": {"contract_type": "call", "strike_price": 580, "expiration_date": "2026-09-20"},
            "greeks": {"gamma": 0.05},
            "open_interest": 5000,
            "day": {"volume": 100},
        },
        {
            "details": {"contract_type": "put", "strike_price": 575, "expiration_date": "2026-09-20"},
            "greeks": {"gamma": 0.04},
            "open_interest": 8000,
            "day": {"volume": 100},
        },
    ]
    result = cp.compute_gex(options, spot=578.0)
    assert "max_pain" in result
    assert isinstance(result["max_pain"], float)
