"""Unit tests: pickup overdue alert.

Spec §6.7 — Alert fires when actual pickup time exceeds pickup_phase end
plus the configured threshold (default: 3 hours).
Alert fires exactly once per reservation (pickup_overdue_alerted flag).
"""

import pytest
from datetime import datetime, timedelta, timezone
from app.services.overdue import is_pickup_overdue


@pytest.mark.parametrize("scheduled_hour,minutes_past,is_overdue", [
    # Pickup at 10:00 (Morning), threshold = 3h → overdue at 13:00
    (10, 179, False),  # 12:59 — not yet
    (10, 180, True),   # 13:00 — exactly at threshold
    (10, 181, True),   # 13:01 — past threshold
    (10, 240, True),   # 14:00 — well past
])
def test_overdue_at_threshold_boundary(scheduled_hour, minutes_past, is_overdue):
    pickup = datetime(2026, 5, 5, scheduled_hour, 0, 0, tzinfo=timezone.utc)
    now = pickup + timedelta(minutes=minutes_past)
    assert is_pickup_overdue(pickup, now, threshold_hours=3) == is_overdue


def test_overdue_does_not_fire_before_threshold():
    pickup = datetime(2026, 5, 5, 14, 0, 0, tzinfo=timezone.utc)
    just_before = pickup + timedelta(hours=2, minutes=59, seconds=59)
    assert is_pickup_overdue(pickup, just_before, threshold_hours=3) is False


def test_overdue_fires_exactly_at_threshold():
    pickup = datetime(2026, 5, 5, 14, 0, 0, tzinfo=timezone.utc)
    exactly_at = pickup + timedelta(hours=3)
    assert is_pickup_overdue(pickup, exactly_at, threshold_hours=3) is True


def test_configurable_threshold_respected():
    pickup = datetime(2026, 5, 5, 9, 0, 0, tzinfo=timezone.utc)
    two_hours_later = pickup + timedelta(hours=2)
    assert is_pickup_overdue(pickup, two_hours_later, threshold_hours=1) is True
    assert is_pickup_overdue(pickup, two_hours_later, threshold_hours=3) is False


def test_night_phase_pickup_never_overdue():
    """Pickups in Night phase are not permitted; overdue check must return False."""
    pickup = datetime(2026, 5, 5, 2, 0, 0, tzinfo=timezone.utc)  # Night
    well_past = pickup + timedelta(hours=10)
    assert is_pickup_overdue(pickup, well_past) is False
