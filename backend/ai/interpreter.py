import json
import logging
from datetime import datetime, timezone
from groq import AsyncGroq

logger = logging.getLogger(__name__)

MODEL = "qwen/qwen3.8-27b"

SYSTEM_PROMPT = """You are a professional U.S. equity market analyst. Your job is to interpret real-time market microstructure data and provide actionable intraday price range predictions.

Always respond with a single JSON object. No markdown, no explanation outside the JSON. No <think> tags. The JSON must contain exactly these keys: support (float), resistance (float), bias (string: bullish/bearish/neutral), key_level (float), trigger_long (string), trigger_short (string), confidence (string: high/medium/low), summary (string, max 100 Chinese characters)."""


class Interpreter:
    def __init__(self, api_key: str):
        self._client = AsyncGroq(api_key=api_key) if api_key else None

    async def interpret(self, data: dict, symbol: str = "SPY") -> dict:
        if not self._client:
            return {"bias": "unknown", "error": "no API key", "summary": "未配置 AI key"}
        user_content = self._build_prompt(data, symbol)
        try:
            response = await self._client.chat.completions.create(
                model=MODEL,
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )
            raw = response.choices[0].message.content.strip()
            if "<think>" in raw:
                raw = raw[raw.rfind("</think>") + 8:].strip()
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Groq returned invalid JSON: {e} — raw: {raw[:200]}")
            return {"bias": "unknown", "error": str(e), "summary": "解读失败"}
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            return {"bias": "unknown", "error": str(e), "summary": "API 错误"}

    def _build_prompt(self, d: dict, symbol: str = "SPY") -> str:
        now_utc = datetime.now(timezone.utc)
        market_time = now_utc.strftime("%H:%M UTC")
        spot = d.get("spot")
        gex_net = d.get("gex_net", 0) or 0
        if abs(gex_net) >= 1e9:
            gex_str = f"{gex_net / 1e9:+.2f}B"
        else:
            gex_str = f"{gex_net / 1e6:+.0f}M"
        lines = [
            f"标的: {symbol} | 时间: {market_time}",
            f"现价: {spot}",
            f"VPOC: {d.get('vpoc')} | VAH: {d.get('vah')} | VAL: {d.get('val')} | VPOC偏向: {d.get('vpoc_bias')}",
            f"GEX信号: {d.get('gex_signal')} | GEX净值: {gex_str} | 最大痛点: {d.get('max_pain')}",
            f"OI PCR: {d.get('oi_pcr')} ({d.get('oi_pcr_signal')}) | Volume PCR: {d.get('vol_pcr')} ({d.get('vol_pcr_signal')})",
            f"VIX: {d.get('vix')} | VVIX/VIX: {d.get('vvix_ratio', 'N/A')}",
        ]
        if d.get("options_alerts"):
            for a in d["options_alerts"][:3]:
                otm = f"{a.get('otm_pct', 0):.1f}% OTM" if a.get("otm_pct") else "ATM"
                lines.append(
                    f"期权异动: {a.get('contract_type','').upper()} "
                    f"${a.get('strike')} {a.get('expiry','')} "
                    f"premium=${a.get('premium', 0) / 1e6:.1f}M {otm}"
                )
        if d.get("top_headlines"):
            lines.append(f"新闻摘要: {' | '.join(d['top_headlines'][:3])}")
        lines.append("\n请输出JSON格式的分析结果，包含今日支撑位、压力位、方向偏向、关键触发价位。")
        return "\n".join(lines)
