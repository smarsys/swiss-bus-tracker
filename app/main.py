import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.cache import TTLCache
from app.models import Departure, StopMatch
from app.ojp_client import OJPError, get_stop_events, search_stops

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

VERSION = "0.3.0"

app = FastAPI(title="Swiss Bus Tracker", version=VERSION)

cors_origins = os.getenv("CORS_ORIGINS", "")
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in cors_origins.split(",")],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
cache = TTLCache(ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "20")))


@app.get("/health")
async def health():
    return {"status": "ok", "version": VERSION}


@app.get("/api/debug/now")
async def debug_now():
    utc_now = datetime.now(timezone.utc)
    naive_now = datetime.now()
    local_tz_name = time.tzname[time.daylight] if time.daylight else time.tzname[0]
    return {
        "server_now_utc_iso": utc_now.isoformat(),
        "server_now_local_iso": utc_now.astimezone().isoformat(),
        "server_tz": local_tz_name,
        "python_naive_now_iso_BAD": naive_now.isoformat(),
    }


@app.get("/api/stops/search", response_model=list[StopMatch])
async def api_search_stops(
    q: str = Query(..., min_length=2, description="Stop name to search"),
    limit: int = Query(10, ge=1, le=50),
):
    try:
        return await search_stops(q, limit)
    except OJPError as e:
        raise HTTPException(status_code=502, detail=str(e))


OJP_FETCH_SIZE = 50


@app.get("/api/departures", response_model=list[Departure])
async def api_departures(
    stop_ref: str = Query(..., alias="stopRef"),
    line: str | None = Query(None),
    direction: str | None = Query(None),
    window_min: int = Query(60, ge=1, le=360),
    num_results: int = Query(5, ge=1, le=50),
):
    cache_key = f"departures:{stop_ref}:{window_min}"
    lock = cache.get_lock(cache_key)
    async with lock:
        cached = cache.get(cache_key)
        if cached is not None:
            departures = cached
        else:
            try:
                departures = await get_stop_events(stop_ref, window_min, OJP_FETCH_SIZE)
            except OJPError as e:
                raise HTTPException(status_code=502, detail=str(e))
            cache.set(cache_key, departures)

    # Filter by time window
    cutoff = datetime.now(timezone.utc) + timedelta(minutes=window_min)
    departures = [d for d in departures if d.scheduled_time <= cutoff]

    if line:
        departures = [d for d in departures if d.line == line]
    if direction:
        direction_lower = direction.lower()
        departures = [
            d for d in departures
            if direction_lower in d.destination.lower()
            or any(direction_lower in s.lower() for s in d.onward_stops)
        ]

    return departures[:num_results]


@app.get("/static/sw.js")
async def service_worker():
    return FileResponse(
        str(STATIC_DIR / "sw.js"),
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))
