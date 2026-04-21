from datetime import datetime, timezone
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


def _make_departure(line: str, destination: str, position_min: int) -> Departure:
    base = datetime(2026, 4, 21, 10, 0, 0, tzinfo=timezone.utc)
    scheduled = base.replace(minute=position_min)
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
