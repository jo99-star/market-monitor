import pytest
import time
from unittest.mock import AsyncMock, patch
from backend.notifier.discord import DiscordNotifier


async def test_sends_whale_embed():
    notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
    alert = {"symbol": "SPY", "side": "buy", "notional": 55_000_000, "level": "whale", "timestamp": 1700000000000}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 204
        mock_post.return_value.raise_for_status = lambda: None
        await notifier.send_block_alert(alert)

    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert len(payload["embeds"]) == 1
    assert "SPY" in payload["embeds"][0]["title"]


async def test_respects_cooldown():
    notifier = DiscordNotifier(webhook_url="https://discord.com/test", cooldown_seconds=300)
    notifier._last_sent["block:SPY"] = time.time()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        await notifier.send_block_alert({"symbol": "SPY", "side": "buy", "notional": 60_000_000, "level": "whale", "timestamp": 0})

    mock_post.assert_not_called()


async def test_sell_side_uses_red_color():
    notifier = DiscordNotifier(webhook_url="https://discord.com/test")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.raise_for_status = lambda: None
        await notifier.send_block_alert({"symbol": "SPY", "side": "sell", "notional": 25_000_000, "level": "alert", "timestamp": 0})

    payload = mock_post.call_args.kwargs["json"]
    assert payload["embeds"][0]["color"] == 0xEF4444
