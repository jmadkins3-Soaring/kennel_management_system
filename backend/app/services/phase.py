"""Phase derivation service.

Phase windows (from phases.json):
  Night:     00:00 – 05:59
  Morning:   06:00 – 11:59
  Afternoon: 12:00 – 17:59
  Evening:   18:00 – 23:59

Post-checkout hold mapping (Spec §6.2):
  Morning checkout  → Afternoon hold → Evening available
  Afternoon checkout → Evening hold  → next Morning available
  Evening checkout  → Night hold    → next Morning available
  Night: no checkouts permitted
"""

from datetime import datetime, time
from typing import TYPE_CHECKING

# Implemented by Agent B (PACFA & Phase Engine stream)


def get_phase(dt: datetime) -> str:
    """Return phase name for a given datetime. Handles both naive and tz-aware datetimes."""
    # Strip tzinfo so hour comparison is always against local/wall time
    h = dt.hour
    if h < 6:
        return "Night"
    elif h < 12:
        return "Morning"
    elif h < 18:
        return "Afternoon"
    else:
        return "Evening"


def get_hold_phase(checkout_phase: str) -> str:
    """Return the hold phase that follows a given checkout phase."""
    _mapping = {
        "Morning": "Afternoon",
        "Afternoon": "Evening",
        "Evening": "Night",
    }
    if checkout_phase == "Night":
        raise ValueError("Night phase does not permit checkouts; no hold phase exists.")
    try:
        return _mapping[checkout_phase]
    except KeyError:
        raise ValueError(f"Unknown checkout phase: {checkout_phase!r}")


def get_next_available_phase(checkout_phase: str) -> tuple[str, int]:
    """Return (phase_name, days_offset) when kennel becomes free after checkout."""
    # Morning  → hold Afternoon → available Evening same day (offset 0)
    # Afternoon → hold Evening  → skip Night  → available Morning next day (offset 1)
    # Evening  → hold Night    → skip Night  → available Morning next day (offset 1)
    _mapping = {
        "Morning":   ("Evening", 0),
        "Afternoon": ("Morning", 1),
        "Evening":   ("Morning", 1),
    }
    if checkout_phase not in _mapping:
        raise ValueError(f"Unknown or non-permitted checkout phase: {checkout_phase!r}")
    return _mapping[checkout_phase]


def compute_stay_duration_days(dropoff: datetime, pickup: datetime) -> int:
    """Return number of calendar days from dropoff to pickup (inclusive start, exclusive end)."""
    return (pickup.date() - dropoff.date()).days


def get_pacfa_multiplier(stay_days: int, has_daily_qualifying_activity: bool = False) -> float:
    """Return PACFA sqft multiplier based on stay duration and 181+ day activity exception."""
    if stay_days < 5:
        return 1.0
    elif stay_days <= 30:
        return 1.5
    elif stay_days <= 180:
        return 2.0
    else:
        # 181+ days
        if has_daily_qualifying_activity:
            return 2.0
        return 3.0
