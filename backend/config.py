from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    polygon_api_key: str
    groq_api_key: str = ""
    discord_webhook_url: str
    redis_url: str
    newsapi_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "market-monitor/1.0"
    symbols: list[str] = ["SPY", "QQQ"]

    stock_alert_threshold: float = 20_000_000
    stock_whale_threshold: float = 50_000_000
    options_alert_threshold: float = 500_000
    options_whale_threshold: float = 1_000_000
    gex_neutral_threshold: float = 500_000_000
    block_window_seconds: int = 30
    options_refresh_minutes: int = 10
    snapshot_ttl_seconds: int = 86400
    discord_cooldown_seconds: int = 300

    model_config = {"env_file": ".env"}
