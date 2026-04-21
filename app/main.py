import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.cache import TTLCache
from app.models import Departure, StopMatch
from app.ojp_client import OJPError, get_stop_events, search_stops

load_dotenv()

app = FastAPI(title="Swiss Bus Tracker", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
cache = TTLCache(ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "20")))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/stops/search", response_model=list[StopMatch])
async def api_search_stops(
    q: str = Query(..., min_length=2, description="Stop name to search"),
    limit: int = Query(10, ge=1, le=50),
):
    try:
        return await search_stops(q, limit)
    except OJPError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/departures", response_model=list[Departure])
async def api_departures(
    stop_ref: str = Query(..., alias="stopRef"),
    line: str | None = Query(None),
    direction: str | None = Query(None),
    window_min: int = Query(60, ge=1, le=360),
    num_results: int = Query(10, ge=1, le=50),
):
    cache_key = f"departures:{stop_ref}:{window_min}:{num_results}"
    lock = cache.get_lock(cache_key)
    async with lock:
        cached = cache.get(cache_key)
        if cached is not None:
            departures = cached
        else:
            try:
                departures = await get_stop_events(stop_ref, window_min, num_results)
            except OJPError as e:
                raise HTTPException(status_code=502, detail=str(e))
            cache.set(cache_key, departures)

    if line:
        departures = [d for d in departures if d.line == line]
    if direction:
        direction_lower = direction.lower()
        departures = [d for d in departures if direction_lower in d.destination.lower()]

    return departures


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))
