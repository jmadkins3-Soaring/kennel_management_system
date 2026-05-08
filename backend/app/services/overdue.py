"""Pickup overdue detection service (Spec §6.7).

Alert fires when actual pickup time exceeds scheduled pickup_datetime
plus the configured threshold (default 3 hours from system.json).
Alert fires once per reservation — the pickup_overdue_alerted flag tracks dismissal.
"""

from datetime import datetime, timedelta

from .phase import get_phase


def is_pickup_overdue(
    scheduled_pickup: datetime,
    current_time: datetime,
    threshold_hours: int = 3,
) -> bool:
    """
    Return True if current_time is at or past scheduled_pickup + threshold_hours.

    Night-phase pickups always return False — night checkouts are not permitted,
    so they can never be overdue.
    """
    if get_phase(scheduled_pickup) == "Night":
        return False
    overdue_at = scheduled_pickup + timedelta(hours=threshold_hours)
    return current_time >= overdue_at
