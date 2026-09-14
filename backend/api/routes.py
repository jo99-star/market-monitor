from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter()
cache = None  # injected at startup via main.py


@router.get("/api/health")
async def health():
    return {"status": "ok"}


@router.get("/api/snapshot")
async def snapshot(symbol: str = Query(default="SPY")):
    data = await cache.read_snapshot(symbol.upper())
    if data is None:
        return JSONResponse(status_code=503, content={"error": "no data available"})
    return data


@router.get("/api/snapshot/all")
async def snapshot_all():
    from backend.config import Settings
    s = Settings(
        polygon_api_key="x",
        anthropic_api_key="x",
        discord_webhook_url="x",
        redis_url="x",
    )
    result = {}
    for sym in s.symbols:
        result[sym.lower()] = await cache.read_snapshot(sym) or {}
    return result
