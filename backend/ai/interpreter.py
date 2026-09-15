import json
import logging
from groq import AsyncGroq

logger = logging.getLogger(__name__)

MODEL = "qwen/qwen3.8-27b"

SYSTEM_PROMPT = """You are a professional U.S. equity market analyst specializing in SPY and QQQ intraday flow analysis. Your job is to interpret real-time market microstructure data and provide actionable intraday price range predictions.

Always respond with a single JSON object. No markdown, no explanation outside the JSON. No <think> tags. The JSON must contain exactly these keys: support (float), resistance (float), bias (string: bullish/bearish/neutral), key_level (float), trigger_long (string), trigger_short (string), confidence (string: high/medium/low), summary (string, max 100 Chinese characters)."""


class Interpreter:
    def __init__(self, api_key: str):
        self._client = AsyncGroq(api_key=api_key) if api_key else None

    async def interpret(self, data: dict) -> dict:
        if not self._client:
            return {"bias": "unknown", "error": "no API key", "summary": "未配置 AI key"}
        user_content = self._build_prompt(data)
        try:
            response = await self._client.chat.completions.create(
                model=MODEL,
                max_tokens=512,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )
            raw = response.choices[0].message.content.strip()
            # Strip any <think>...</think> blocks (Qwen reasoning models)
            if "<think>" in raw:
                raw = raw[raw.rfind("</think>") + 8:].strip()
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Groq returned invalid JSON: {e} — raw: {raw[:200]}")
            return {"bias": "unknown", "error": str(e), "summary": "解读失败"}
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            return {"bias": "unknown", "error": str(e), "summary": "API 错误"}

    def _build_prompt(self, d: dict) -> str:
        spot = d.get("spot")
        lines = [
            f"现价: {spot}",
            f"VPOC: {d.get('vpoc')} | VAH: {d.get('vah')} | VAL: {d.get('val')} | VPOC偏向: {d.get('vpoc_bias')}",
            f"GEX信号: {d.get('gex_signal')} | GEX净值: {d.get('gex_net', 0):.0f} | 最大痛点: {d.get('max_pain')}",
            f"OI PCR: {d.get('oi_pcr')} ({d.get('oi_pcr_signal')}) | Volume PCR: {d.get('vol_pcr')} ({d.get('vol_pcr_signal')})",
            f"VIX: {d.get('vix')} | VVIX/VIX: {d.get('vvix_ratio', 'N/A')}",
        ]
        if d.get("options_alerts"):
            lines.append(f"期权异动(前3): {json.dumps(d['options_alerts'][:3], ensure_ascii=False)}")
        if d.get("top_headlines"):
            lines.append(f"新闻摘要: {' | '.join(d['top_headlines'][:3])}")

        lines.append("\n请输出JSON格式的分析结果，包含今日支撑位、压力位、方向偏向、关键触发价位。")
        return "\n".join(lines)
