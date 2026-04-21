import asyncio
import time
from datetime import datetime, timezone

from app.cache import TTLCache
from app.models import Departure, DepartureStatus
from app.ojp_client import parse_location_response, parse_stop_event_response


def test_parse_location_response(location_response_xml):
    stops = parse_location_response(location_response_xml)
    assert len(stops) == 3

    assert stops[0].stop_ref == "8595126"
    assert stops[0].name == "Oulens-sous-Echallens, Collège"
    assert stops[0].locality == "Oulens-sous-Echallens"
    assert abs(stops[0].lat - 46.63456) < 0.001
    assert abs(stops[0].lon - 6.63244) < 0.001

    assert stops[1].stop_ref == "8595127"
    assert stops[2].stop_ref == "8595128"
    assert stops[2].name == "Echallens, gare"


def test_parse_stop_event_response(stop_event_response_xml):
    # Use a "now" that is before both departures so nothing is "already passed"
    now = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)
    deps = parse_stop_event_response(stop_event_response_xml, now=now)
    assert len(deps) == 2

    # First: has delay (estimated 12:35 vs planned 12:32 = 3 min)
    d1 = deps[0]
    assert d1.line == "425"
    assert d1.destination == "Échallens, gare"
    assert d1.delay_minutes == 3
    assert d1.status == DepartureStatus.delayed
    assert d1.already_passed is False
    assert d1.mode == "bus"

    # Second: no estimated time → scheduled status, 0 delay
    d2 = deps[1]
    assert d2.line == "425"
    assert d2.destination == "Lausanne-Flon"
    assert d2.delay_minutes == 0
    assert d2.status == DepartureStatus.scheduled
    assert d2.estimated_time is None


def test_already_passed_logic():
    now = datetime(2026, 4, 21, 15, 0, 0, tzinfo=timezone.utc)
    dep = Departure(
        line="425",
        destination="Test",
        scheduled_time=datetime(2026, 4, 21, 14, 30, 0, tzinfo=timezone.utc),
        estimated_time=datetime(2026, 4, 21, 14, 33, 0, tzinfo=timezone.utc),
    )
    dep.compute_status_and_delay(now)
    assert dep.already_passed is True
    assert dep.delay_minutes == 3
    assert dep.status == DepartureStatus.delayed

    # Future departure
    dep2 = Departure(
        line="381",
        destination="Test2",
        scheduled_time=datetime(2026, 4, 21, 16, 0, 0, tzinfo=timezone.utc),
        estimated_time=datetime(2026, 4, 21, 16, 0, 0, tzinfo=timezone.utc),
    )
    dep2.compute_status_and_delay(now)
    assert dep2.already_passed is False
    assert dep2.status == DepartureStatus.on_time


def test_parse_real_stop_event_response():
    """Parse a real OJP response (no realtime data → all scheduled)."""
    from pathlib import Path
    xml = (Path(__file__).parent / "fixtures" / "real_stop_event_response.xml").read_bytes()
    now = datetime(2026, 4, 21, 9, 0, 0, tzinfo=timezone.utc)
    deps = parse_stop_event_response(xml, now=now)
    assert len(deps) == 5
    for d in deps:
        assert d.line == "425"
        assert d.status == DepartureStatus.scheduled
        assert d.estimated_time is None
        assert d.delay_minutes == 0
        assert d.already_passed is False
        assert d.mode == "bus"
    # Verify sorted by scheduled_time
    times = [d.scheduled_time for d in deps]
    assert times == sorted(times)


def test_scheduled_vs_delayed_status():
    """Scheduled when no estimated, delayed when estimated > scheduled."""
    now = datetime(2026, 4, 21, 10, 0, 0, tzinfo=timezone.utc)
    # No estimated → scheduled
    dep1 = Departure(
        line="1",
        destination="A",
        scheduled_time=datetime(2026, 4, 21, 11, 0, 0, tzinfo=timezone.utc),
    )
    dep1.compute_status_and_delay(now)
    assert dep1.status == DepartureStatus.scheduled
    # Estimated = scheduled → on_time
    dep2 = Departure(
        line="2",
        destination="B",
        scheduled_time=datetime(2026, 4, 21, 11, 0, 0, tzinfo=timezone.utc),
        estimated_time=datetime(2026, 4, 21, 11, 0, 30, tzinfo=timezone.utc),
    )
    dep2.compute_status_and_delay(now)
    assert dep2.status == DepartureStatus.on_time
    assert dep2.delay_minutes == 0


def test_cache_ttl():
    cache = TTLCache(ttl_seconds=1)
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"

    time.sleep(1.1)
    assert cache.get("key1") is None
