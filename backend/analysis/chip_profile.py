from collections import defaultdict
from typing import Optional

BUCKET = 0.10


class ChipProfile:
    def __init__(self, bucket_size: float = BUCKET):
        self._bucket = bucket_size
        self._buckets: dict[float, float] = defaultdict(float)
        self._spot: Optional[float] = None

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
        self._buckets[self._round_bucket(price)] += size

    def set_spot(self, price: float) -> None:
        self._spot = price

    def compute(self) -> dict:
        if not self._buckets:
            return {"vpoc": 0, "vah": 0, "val": 0, "vpoc_bias": "neutral"}

        total_vol = sum(self._buckets.values())
        target = total_vol * 0.70

        vpoc = max(self._buckets, key=self._buckets.__getitem__)

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

    def compute_gex(self, options: list[dict], spot: float, gex_threshold: float = 2_000_000_000) -> dict:
        """GEX = Gamma × OI × 100 × spot; dealer convention: calls −gamma (dealers short), puts +gamma (dealers long)."""
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
            sign = -1 if contract_type == "call" else 1
            gex = sign * gamma * oi * 100 * spot
            gex_net += gex
            gex_by_strike[strike] += gex

        if abs(gex_net) < gex_threshold:
            gex_signal = "neutral"
        elif gex_net > 0:
            gex_signal = "mean_revert"
        else:
            gex_signal = "trend_amplify"

        strikes = sorted({opt["details"]["strike_price"] for opt in options})
        min_pain = float("inf")
        max_pain_strike = float(strikes[0]) if strikes else float(spot)

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
