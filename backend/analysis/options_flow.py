SWEEP_CONDITIONS: set = set()  # Polygon has no reliable sweep condition code; code 71 is "Contingent Trade"


class OptionsFlowScanner:
    def __init__(self, alert_threshold: float, whale_threshold: float):
        self._alert = alert_threshold
        self._whale = whale_threshold

    def _estimate_premium(self, opt: dict) -> float:
        last = opt.get("last_trade") or {}
        price = last.get("price", 0) or 0
        day_vol = (opt.get("day") or {}).get("volume", 0) or 0
        return price * day_vol * 100  # total daily premium proxy (last price × daily volume)

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
            ticker = details.get("ticker", "")
            symbol = ticker.split(":")[1][:3] if ":" in ticker else ticker[:3]
            alerts.append({
                "symbol": symbol,
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
