from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def location_response_xml():
    return (FIXTURES_DIR / "location_response.xml").read_bytes()


@pytest.fixture
def stop_event_response_xml():
    return (FIXTURES_DIR / "stop_event_response.xml").read_bytes()
