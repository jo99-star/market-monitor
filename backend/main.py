import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import Settings
from backend.api import routes
from backend.cache.redis_cache import RedisCache
from backend.data.polygon_rest import PolygonREST
from backend.data.polygon_ws import PolygonWebSocket
from backend.analysis.block_detector import BlockDetector
from backend.analysis.chip_profile import ChipProfile
from backend.analysis.options_flow import OptionsFlowScanner
from backend.analysis.sentiment import SentimentAnalyzer
from backend.ai.call_queue import CallQueue
from backend.ai.interpreter import Interpreter
from backend.notifier.discord import DiscordNotifier
from backend.scheduler import MarketScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()

_cache = RedisCache(url=settings.redis_url, ttl=settings.snapshot_ttl_seconds)
_rest = PolygonREST(api_key=settings.polygon_api_key)

# Per-symbol block detectors with calibrated thresholds
_block_det = {
    s: BlockDetector(
        settings.block_window_seconds,
        settings.block_thresholds.get(s, {}).get("whale", settings.stock_whale_threshold),
        settings.block_thresholds.get(s, {}).get("alert", settings.stock_alert_threshold),
    )
    for s in settings.symbols
}

_chip = {s: ChipProfile() for s in settings.symbols}

# Per-symbol options flow scanners with calibrated thresholds
_options_scanner = {
    s: OptionsFlowScanner(
        settings.options_thresholds.get(s, {}).get("alert", settings.options_alert_threshold),
        settings.options_thresholds.get(s, {}).get("whale", settings.options_whale_threshold),
    )
    for s in settings.symbols
}

_sentiment = SentimentAnalyzer()
_discord = DiscordNotifier(settings.discord_webhook_url, settings.discord_cooldown_seconds)
_interpreter = Interpreter(api_key=settings.groq_api_key)

# Flag to skip options refresh while premarket job is populating chip profiles
_premarket_running: bool = False


async def _handle_ai_task(task: dict) -> None:
    task_type = task.get("type")
    sym = task.get("symbol", settings.symbols[0])
    if task_type == "premarket":
        snap = task.get("data", {})
        interp = await _interpreter.interpret(snap, symbol=sym)
        existing = await _cache.read_snapshot(sym) or {}
        existing["interpretation"] = interp
        await _cache.write_snapshot(sym, existing)
        pcr = {"oi_pcr": snap.get("oi_pcr"), "oi_pcr_signal": snap.get("oi_pcr_signal")}
        if sym == settings.symbols[0]:  # send Discord premarket report for primary symbol only
            await _discord.send_premarket_report(sym, interp, pcr, snap.get("vix", 0), snap.get("events", []))
    elif task_type == "hourly":
        snap = await _cache.read_snapshot(sym) or {}
        interp = await _interpreter.interpret(snap, symbol=sym)
        snap["interpretation"] = interp
        await _cache.write_snapshot(sym, snap)
        await _discord.send_hourly_brief(sym, snap)
    elif task_type == "close":
        snap = await _cache.read_snapshot(sym) or {}
        interp = await _interpreter.interpret(snap, symbol=sym)
        snap["interpretation"] = interp
        await _cache.write_snapshot(sym, snap)
        if sym == settings.symbols[0]:  # send Discord close summary for primary symbol only
            await _discord.send_closing_summary({sym: snap}, interp)


_call_queue = CallQueue(handler=_handle_ai_task)


def _fire_task(coro) -> None:
    task = asyncio.create_task(coro)
    task.add_done_callback(
        lambda t: logger.error(f"Background task failed: {t.exception()}")
        if not t.cancelled() and t.exception() else None
    )


def _on_tick(tick: dict) -> None:
    sym = tick.get("sym")
    if sym not in _block_det:
        return
    _block_det[sym].ingest(tick)
    _chip[sym].add_tick(tick["p"], tick["s"])
    alerts = _block_det[sym].flush_alerts()
    for alert in alerts:
        if alert["level"] == "whale":
            # Check cooldown before creating tasks to avoid unnecessary coroutine churn
            if _discord._can_send(f"block:{sym}"):
                _fire_task(_discord.send_block_alert(alert))
            _fire_task(_call_queue.enqueue({"priority": "whale", "type": "whale_block", "data": alert}))


_ws = PolygonWebSocket(api_key=settings.polygon_api_key, symbols=settings.symbols)
_ws.on_tick = _on_tick


async def _premarket_job() -> None:
    global _premarket_running
    _premarket_running = True
    _discord.reset_alerted_set()  # fresh alert dedup each trading day
    logger.info("Running pre-market job")
    try:
        vix_data = await _rest.get_vix()
        news = await _rest.get_news(settings.symbols)
        headlines = [a.get("title", "") for a in news[:5]]
        snaps = {}
        for sym in settings.symbols:
            try:
                _chip[sym] = ChipProfile()
                bars = await _rest.get_daily_bars(sym, days=20)
                if len(bars) < 5:
                    logger.warning(f"Only {len(bars)} bars returned for {sym}")
                for bar in bars:
                    _chip[sym].add_bar(bar)
                spot = await _rest.get_spot_price(sym)
                _chip[sym].set_spot(spot)
                options = await _rest.get_options_snapshot(sym)
                chip_result = _chip[sym].compute()
                gex_threshold = settings.gex_thresholds.get(sym, settings.gex_neutral_threshold)
                gex_result = _chip[sym].compute_gex(options, spot, gex_threshold=gex_threshold)
                pcr_thresh = settings.pcr_thresholds.get(sym)
                pcr = _sentiment.compute_pcr(options, thresholds=pcr_thresh)
                flow_alerts = _options_scanner[sym].scan(options, spot)
                snap = {
                    **chip_result, **gex_result, **pcr,
                    "spot": spot,
                    "vix": vix_data.get("vix"),
                    "vvix_ratio": vix_data.get("ratio"),
                    "options_count": len(options),
                    "top_headlines": headlines,
                    "options_alerts": flow_alerts[:10],
                }
                snaps[sym] = snap
                await _cache.write_snapshot(sym, snap)
            except Exception as e:
                logger.error(f"Premarket job failed for {sym}: {e}")
        for sym in snaps:
            await _call_queue.enqueue({"priority": "whale", "type": "premarket", "data": snaps[sym], "symbol": sym})
    finally:
        _premarket_running = False


async def _options_refresh_job() -> None:
    if _premarket_running:
        logger.info("Skipping options refresh — premarket job in progress")
        return
    for sym in settings.symbols:
        try:
            spot = await _rest.get_spot_price(sym)
            options = await _rest.get_options_snapshot(sym)
            gex_threshold = settings.gex_thresholds.get(sym, settings.gex_neutral_threshold)
            gex_result = _chip[sym].compute_gex(options, spot, gex_threshold=gex_threshold)
            pcr_thresh = settings.pcr_thresholds.get(sym)
            pcr = _sentiment.compute_pcr(options, thresholds=pcr_thresh)
            flow_alerts = _options_scanner[sym].scan(options, spot)
            snap = await _cache.read_snapshot(sym) or {}
            snap.update({**gex_result, **pcr, "spot": spot, "options_alerts": flow_alerts[:10]})
            await _cache.write_snapshot(sym, snap)
            for alert in flow_alerts:
                if alert["level"] == "whale":
                    _fire_task(_discord.send_options_alert(alert))
        except Exception as e:
            logger.error(f"Options refresh failed for {sym}: {e}")


async def _hourly_job() -> None:
    for sym in settings.symbols:
        await _call_queue.enqueue({"priority": "regular", "type": "hourly", "symbol": sym})


async def _close_job() -> None:
    for sym in settings.symbols:
        await _call_queue.enqueue({"priority": "whale", "type": "close", "symbol": sym})


_scheduler = MarketScheduler(
    premarket_handler=_premarket_job,
    hourly_handler=_hourly_job,
    close_handler=_close_job,
    options_refresh_handler=_options_refresh_job,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _cache.connect()
    await _call_queue.start()
    _scheduler.start()
    ws_task = asyncio.create_task(_ws.run())
    routes.cache = _cache
    routes.symbols = settings.symbols
    routes.trigger_token = settings.trigger_token
    routes.premarket_handler = _premarket_job
    logger.info("Market monitor started")
    yield
    ws_task.cancel()
    _scheduler.stop()
    await _call_queue.stop()
    await _discord.close()
    await _cache.close()
    await _rest.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(routes.router)
