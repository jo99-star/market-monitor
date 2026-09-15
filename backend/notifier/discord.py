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
        self._last_sent: dict = {}
        self._options_alerted: set = set()  # dedupe options alerts within a session

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
        self._last_sent[key] = time.time()  # set before HTTP to prevent retry storm on 429
        color = COLOR_BULL if alert["side"] == "buy" else COLOR_BEAR
        direction = "买入" if alert["side"] == "buy" else "卖出"
        embed = {
            "title": f"大单异动 — {sym}",
            "color": color,
            "fields": [
                {"name": "方向", "value": direction, "inline": True},
                {"name": "金额", "value": f"${alert['notional'] / 1e6:.1f}M", "inline": True},
                {"name": "级别", "value": "Whale" if alert["level"] == "whale" else "Alert", "inline": True},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._post({"embeds": [embed]})

    async def send_options_alert(self, alert: dict) -> None:
        sym = alert["symbol"]
        key = f"options:{sym}:{alert['strike']}:{alert['contract_type']}:{alert['expiry']}"
        if key in self._options_alerted:
            return
        self._options_alerted.add(key)
        color = COLOR_BULL if alert["contract_type"] == "call" else COLOR_BEAR
        embed = {
            "title": f"期权异动 — {sym}",
            "color": color,
            "fields": [
                {"name": "合约", "value": f"{alert['strike']}{alert['contract_type'].upper()[0]} {alert['expiry']}", "inline": True},
                {"name": "权利金", "value": f"${alert['premium'] / 1e6:.2f}M", "inline": True},
                {"name": "类型", "value": alert["flow_type"].upper(), "inline": True},
                {"name": "IV", "value": f"{alert['iv'] * 100:.1f}%", "inline": True},
                {"name": "OTM", "value": f"{alert['otm_pct']:.1f}%", "inline": True},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._post({"embeds": [embed]})

    async def send_premarket_report(self, interpretation: dict, pcr: dict, vix: float, events: list) -> None:
        embed = {
            "title": "早盘报告",
            "color": (COLOR_BULL if interpretation.get("bias") == "bullish"
                      else COLOR_BEAR if interpretation.get("bias") == "bearish"
                      else COLOR_INFO),
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
            "title": f"每小时简报 — {symbol}",
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
            "title": "收盘总结",
            "color": COLOR_INFO,
            "fields": [
                {"name": "AI收盘摘要", "value": interpretation.get("summary", "N/A"), "inline": False},
                {"name": "预测准确度", "value": interpretation.get("accuracy_note", "待人工评估"), "inline": False},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._post({"embeds": [embed]})
