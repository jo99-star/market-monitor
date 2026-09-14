import pytest
from unittest.mock import AsyncMock
from backend.scheduler import MarketScheduler


def test_registers_three_job_types():
    scheduler = MarketScheduler(
        premarket_handler=AsyncMock(),
        hourly_handler=AsyncMock(),
        close_handler=AsyncMock(),
    )
    scheduler.setup()
    jobs = scheduler._scheduler.get_jobs()
    job_ids = [j.id for j in jobs]
    assert "premarket" in job_ids
    assert "close" in job_ids
    assert any("hourly" in jid for jid in job_ids)


def test_registers_options_refresh_when_provided():
    scheduler = MarketScheduler(
        premarket_handler=AsyncMock(),
        hourly_handler=AsyncMock(),
        close_handler=AsyncMock(),
        options_refresh_handler=AsyncMock(),
    )
    scheduler.setup()
    job_ids = [j.id for j in scheduler._scheduler.get_jobs()]
    assert "options_refresh" in job_ids


def test_six_hourly_jobs_registered():
    scheduler = MarketScheduler(
        premarket_handler=AsyncMock(),
        hourly_handler=AsyncMock(),
        close_handler=AsyncMock(),
    )
    scheduler.setup()
    job_ids = [j.id for j in scheduler._scheduler.get_jobs()]
    hourly_jobs = [jid for jid in job_ids if "hourly" in jid]
    assert len(hourly_jobs) == 6  # 10, 11, 12, 13, 14, 15
