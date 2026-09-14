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
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_content}],
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
