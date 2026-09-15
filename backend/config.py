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
    symbols: list[str] = ["SPY", "QQQ", "SOXX"]

    # Scalar fallback thresholds (used if symbol not in per-symbol dicts below)
    stock_alert_threshold: float = 20_000_000
    stock_whale_threshold: float = 50_000_000
    options_alert_threshold: float = 500_000
    options_whale_threshold: float = 1_000_000
    gex_neutral_threshold: float = 2_000_000_000
    block_window_seconds: int = 30
    options_refresh_minutes: int = 10
    snapshot_ttl_seconds: int = 86400
    discord_cooldown_seconds: int = 300

    # Per-symbol GEX neutral thresholds
    gex_thresholds: dict = {
        "SPY":  2_000_000_000,
        "QQQ":    750_000_000,
        "SOXX":    75_000_000,
    }

    # Per-symbol PCR signal thresholds
    pcr_thresholds: dict = {
        "SPY":  {"oi_bull": 1.2, "oi_bear": 1.8, "vol_bull": 0.90, "vol_bear": 1.1},
        "QQQ":  {"oi_bull": 1.1, "oi_bear": 1.6, "vol_bull": 0.85, "vol_bear": 1.0},
        "SOXX": {"oi_bull": 0.7, "oi_bear": 1.1, "vol_bull": 0.70, "vol_bear": 1.0},
    }

    # Per-symbol stock block thresholds
    block_thresholds: dict = {
        "SPY":  {"alert": 100_000_000, "whale": 500_000_000},
        "QQQ":  {"alert":  50_000_000, "whale": 200_000_000},
        "SOXX": {"alert":  10_000_000, "whale":  25_000_000},
    }

    # Per-symbol options flow thresholds
    options_thresholds: dict = {
        "SPY":  {"alert": 5_000_000, "whale": 10_000_000},
        "QQQ":  {"alert": 3_000_000, "whale":  5_000_000},
        "SOXX": {"alert":   500_000, "whale":  1_000_000},
    }

    cors_origins: list[str] = [
        "https://amazing-shortbread-e27dbd.netlify.app",
        "http://localhost:3000",
    ]
    trigger_token: str = ""  # if non-empty, /api/trigger/premarket requires X-Admin-Token

    model_config = {"env_file": ".env"}
