from backend.config import Settings


def test_settings_defaults():
    s = Settings(
        polygon_api_key="key",
        discord_webhook_url="https://discord.com/test",
        redis_url="redis://localhost:6379",
    )
    assert s.symbols == ["SPY", "QQQ"]
    assert s.stock_whale_threshold == 50_000_000
    assert s.options_whale_threshold == 1_000_000
    assert s.block_window_seconds == 30
    assert s.options_refresh_minutes == 10
    assert s.gex_neutral_threshold == 500_000_000
