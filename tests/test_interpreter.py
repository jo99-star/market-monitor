import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from backend.ai.interpreter import Interpreter


async def test_returns_structured_output():
    interp = Interpreter(api_key="test_key")
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "support": 576, "resistance": 588, "bias": "bullish",
        "key_level": 583, "trigger_long": "hold 578 VPOC",
        "trigger_short": "break 578", "confidence": "medium",
        "summary": "Large call sweep + GEX mean-revert favors upside.",
    }))]

    with patch.object(interp._client.messages, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await interp.interpret({
            "spy_spot": 583.4, "vpoc": 578, "vah": 585, "val": 574,
            "gex_signal": "mean_revert", "oi_pcr": 0.9, "vol_pcr": 0.85,
            "vix": 18.2, "vvix_ratio": 1.1, "bias": "bullish",
            "top_headlines": [], "options_alerts": [],
        })

    assert result["support"] == 576
    assert result["resistance"] == 588
    assert result["confidence"] == "medium"


async def test_handles_invalid_json_gracefully():
    interp = Interpreter(api_key="test_key")
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="not valid json")]

    with patch.object(interp._client.messages, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await interp.interpret({"spy_spot": 580})

    assert result["bias"] == "unknown"
    assert "error" in result
