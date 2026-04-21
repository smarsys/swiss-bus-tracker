from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app, cache
from app.models import Departure, DepartureStatus


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def _make_departure(
    line: str, destination: str, position_min: int = 0, onward_stops: list[str] | None = None,
    base: datetime | None = None,
) -> Departure:
    if base is None:
        base = datetime(2026, 4, 21, 10, 0, 0, tzinfo=timezone.utc)
    scheduled = base + timedelta(minutes=position_min)
    return Departure(
        line=line,
        destination=destination,
        scheduled_time=scheduled,
        estimated_time=None,
        delay_minutes=0,
        status=DepartureStatus.scheduled,
        already_passed=False,
        stop_name="Test Stop",
        mode="rail",
        onward_stops=onward_stops or [],
    )


def _mock_departures():
    """20 departures, IR15 at position 15, S1 Yverdon at position 8."""
    deps = []
    for i in range(20):
        if i == 14:
            deps.append(_make_departure("IR15", "Genève-Aéroport", i))
        elif i == 7:
            deps.append(_make_departure("S1", "Yverdon-les-Bains", i))
        else:
            deps.append(_make_departure("S3", f"Allaman {i}", i))
    return deps


@pytest.fixture
def client():
    return TestClient(app)


def test_filter_line_then_limit(client):
    """IR15 at position 15 must be found even with num_results=5."""
    with patch("app.main.get_stop_events", new_callable=AsyncMock) as mock:
        mock.return_value = _mock_departures()
        resp = client.get("/api/departures?stopRef=123&line=IR15&num_results=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["line"] == "IR15"


def test_filter_direction_then_limit(client):
    """S1 Yverdon at position 8 must be found with direction filter."""
    with patch("app.main.get_stop_events", new_callable=AsyncMock) as mock:
        mock.return_value = _mock_departures()
        resp = client.get("/api/departures?stopRef=123&direction=yverdon&num_results=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["destination"] == "Yverdon-les-Bains"


def test_limit_applied_after_filter(client):
    """Without filters, num_results caps the output."""
    with patch("app.main.get_stop_events", new_callable=AsyncMock) as mock:
        mock.return_value = _mock_departures()
        resp = client.get("/api/departures?stopRef=123&num_results=3")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_direction_filter_matches_onward_stops(client):
    """Direction 'vevey' must match R2→Bex if onward_stops contain 'Vevey'."""
    deps = [
        _make_departure("R2", "Bex", 0, onward_stops=["Vevey", "Montreux", "Bex"]),
        _make_departure("S1", "Yverdon-les-Bains", 5),
        _make_departure("R3", "Vevey", 10),
    ]
    with patch("app.main.get_stop_events", new_callable=AsyncMock) as mock:
        mock.return_value = deps
        resp = client.get("/api/departures?stopRef=123&direction=vevey&num_results=5")
    assert resp.status_code == 200
    data = resp.json()
    lines = [d["line"] for d in data]
    assert "R2" in lines  # matched via onward_stops
    assert "R3" in lines  # matched via destination
    assert "S1" not in lines


def test_respects_time_window(client):
    """With window_min=60, no departure beyond now+60min should be returned."""
    now = datetime.now(timezone.utc)
    deps = [
        _make_departure("S1", "A", 0, base=now),                           # now+0 → in window
        _make_departure("S2", "B", 0, base=now + timedelta(minutes=30)),    # now+30 → in window
        _make_departure("S3", "C", 0, base=now + timedelta(minutes=90)),    # now+90 → OUT
        _make_departure("S4", "D", 0, base=now + timedelta(hours=12)),      # tomorrow → OUT
    ]
    with patch("app.main.get_stop_events", new_callable=AsyncMock) as mock:
        mock.return_value = deps
        resp = client.get("/api/departures?stopRef=123&window_min=60&num_results=50")
    assert resp.status_code == 200
    data = resp.json()
    lines = [d["line"] for d in data]
    assert "S1" in lines
    assert "S2" in lines
    assert "S3" not in lines
    assert "S4" not in lines
