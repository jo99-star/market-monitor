from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter()
cache = None       # injected at startup
symbols: list = [] # injected at startup


@router.get("/api/health")
async def health():
    if cache is None:
        return JSONResponse(status_code=503, content={"status": "starting"})
    try:
        await cache._redis.ping()
    except Exception:
        return JSONResponse(status_code=503, content={"status": "redis_down"})
    return {"status": "ok"}


@router.get("/api/snapshot")
async def snapshot(symbol: str = Query(default="SPY")):
    data = await cache.read_snapshot(symbol.upper())
    if data is None:
        return JSONResponse(status_code=503, content={"error": "no data available"})
    return data


@router.get("/api/snapshot/all")
async def snapshot_all():
    result = {}
    for sym in symbols:
        result[sym.lower()] = await cache.read_snapshot(sym) or {}
    return result
