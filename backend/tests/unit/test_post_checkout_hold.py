"""Unit tests: post-checkout hold phase computation.

Spec §6.2 — Post-Checkout Hold Rule:
  Morning checkout  → Afternoon hold  → Evening next available (same day)
  Afternoon checkout → Evening hold   → Morning next day (Night has no transitions)
  Evening checkout  → Night hold      → Morning next day
  Night checkout    → BLOCKED (no checkouts in Night phase)
"""

import pytest
from app.services.phase import get_hold_phase, get_next_available_phase


@pytest.mark.parametrize("checkout_phase,expected_hold", [
    ("Morning",   "Afternoon"),
    ("Afternoon", "Evening"),
    ("Evening",   "Night"),
])
def test_hold_phase_after_checkout(checkout_phase, expected_hold):
    assert get_hold_phase(checkout_phase) == expected_hold


def test_night_checkout_is_blocked():
    """Night phase does not permit checkouts — must raise ValueError."""
    with pytest.raises(ValueError):
        get_hold_phase("Night")


@pytest.mark.parametrize("checkout_phase,expected_phase,expected_day_offset", [
    ("Morning",   "Evening",  0),   # available Evening same day
    ("Afternoon", "Morning",  1),   # available Morning next day (Night skipped)
    ("Evening",   "Morning",  1),   # available Morning next day
])
def test_next_available_after_hold(checkout_phase, expected_phase, expected_day_offset):
    phase, day_offset = get_next_available_phase(checkout_phase)
    assert phase == expected_phase
    assert day_offset == expected_day_offset


def test_evening_hold_persists_through_night():
    """Evening checkout → Night hold → kennel not available until Morning next day."""
    phase, day_offset = get_next_available_phase("Evening")
    assert phase == "Morning"
    assert day_offset == 1


def test_afternoon_checkout_skips_night_phase():
    """Afternoon checkout → Evening hold → kennel skips Night, available Morning next day."""
    phase, day_offset = get_next_available_phase("Afternoon")
    assert phase == "Morning"
    assert day_offset == 1
