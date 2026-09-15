import logging
from typing import Callable, Awaitable, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class MarketScheduler:
    def __init__(
        self,
        premarket_handler: Callable[[], Awaitable[None]],
        hourly_handler: Callable[[], Awaitable[None]],
        close_handler: Callable[[], Awaitable[None]],
        options_refresh_handler: Optional[Callable[[], Awaitable[None]]] = None,
        timezone: str = "America/New_York",
    ):
        self._premarket = premarket_handler
        self._hourly = hourly_handler
        self._close = close_handler
        self._options_refresh = options_refresh_handler
        self._tz = timezone
        self._scheduler = AsyncIOScheduler(timezone=timezone)

    def setup(self) -> None:
        self._scheduler.add_job(
            self._premarket,
            CronTrigger(hour=9, minute=15, day_of_week="mon-fri", timezone=self._tz),
            id="premarket",
            replace_existing=True,
        )
        for hour in range(10, 16):
            self._scheduler.add_job(
                self._hourly,
                CronTrigger(hour=hour, minute=0, day_of_week="mon-fri", timezone=self._tz),
                id=f"hourly_{hour}",
                replace_existing=True,
            )
        self._scheduler.add_job(
            self._close,
            CronTrigger(hour=16, minute=0, day_of_week="mon-fri", timezone=self._tz),
            id="close",
            replace_existing=True,
        )
        if self._options_refresh:
            # Start at 9:25 (after premarket job at 9:15 has seeded chip profile)
            # Stop after 15:50 to avoid post-close waste
            self._scheduler.add_job(
                self._options_refresh,
                CronTrigger(minute="*/10", hour="10-15", day_of_week="mon-fri", timezone=self._tz),
                id="options_refresh",
                replace_existing=True,
            )
            self._scheduler.add_job(
                self._options_refresh,
                CronTrigger(hour=9, minute="25,35,45,55", day_of_week="mon-fri", timezone=self._tz),
                id="options_refresh_9xx",
                replace_existing=True,
            )

    def start(self) -> None:
        self.setup()
        self._scheduler.start()
        logger.info("Scheduler started")

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
