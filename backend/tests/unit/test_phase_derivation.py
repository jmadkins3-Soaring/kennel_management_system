"""Unit tests: phase derivation from datetime.

Spec §6.1 — Phase windows (from phases.json defaults):
  Night:     00:00–05:59
  Morning:   06:00–11:59
  Afternoon: 12:00–17:59
  Evening:   18:00–23:59

ALL boundary minutes must be tested exactly.
"""

import pytest
from datetime import datetime
from app.services.phase import get_phase


# ── Parametrized boundary table ────────────────────────────────────────────────

@pytest.mark.parametrize("hour,minute,second,expected_phase", [
    # Night window
    (0,  0,  0,  "Night"),
    (0,  0,  1,  "Night"),
    (3,  30, 0,  "Night"),
    (5,  59, 59, "Night"),
    # Morning window — starts exactly at 06:00:00
    (6,  0,  0,  "Morning"),
    (6,  0,  1,  "Morning"),
    (9,  0,  0,  "Morning"),
    (11, 59, 59, "Morning"),
    # Afternoon window — starts exactly at 12:00:00
    (12, 0,  0,  "Afternoon"),
    (12, 0,  1,  "Afternoon"),
    (14, 30, 0,  "Afternoon"),
    (17, 59, 59, "Afternoon"),
    # Evening window — starts exactly at 18:00:00
    (18, 0,  0,  "Evening"),
    (18, 0,  1,  "Evening"),
    (21, 0,  0,  "Evening"),
    (23, 59, 59, "Evening"),
])
def test_phase_from_time(hour, minute, second, expected_phase):
    dt = datetime(2026, 5, 5, hour, minute, second)
    assert get_phase(dt) == expected_phase


def test_phase_midnight_is_night():
    assert get_phase(datetime(2026, 5, 5, 0, 0, 0)) == "Night"


def test_phase_last_second_of_night():
    assert get_phase(datetime(2026, 5, 5, 5, 59, 59)) == "Night"


def test_phase_first_second_of_morning():
    assert get_phase(datetime(2026, 5, 5, 6, 0, 0)) == "Morning"


def test_phase_last_second_of_morning():
    assert get_phase(datetime(2026, 5, 5, 11, 59, 59)) == "Morning"


def test_phase_first_second_of_afternoon():
    assert get_phase(datetime(2026, 5, 5, 12, 0, 0)) == "Afternoon"


def test_phase_last_second_of_afternoon():
    assert get_phase(datetime(2026, 5, 5, 17, 59, 59)) == "Afternoon"


def test_phase_first_second_of_evening():
    assert get_phase(datetime(2026, 5, 5, 18, 0, 0)) == "Evening"


def test_phase_last_second_of_evening():
    assert get_phase(datetime(2026, 5, 5, 23, 59, 59)) == "Evening"


def test_phase_handles_timezone_aware_datetime():
    """get_phase must work with both naive and tz-aware datetimes."""
    from datetime import timezone
    dt_aware = datetime(2026, 5, 5, 9, 0, 0, tzinfo=timezone.utc)
    assert get_phase(dt_aware) == "Morning"
