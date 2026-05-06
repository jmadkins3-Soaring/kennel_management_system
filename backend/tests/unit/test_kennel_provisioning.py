"""Unit tests: kennel config provisioning on startup.

Spec §6.9 — On every startup the backend reads kennels.json and reconciles
kennel records. New kennels are auto-provisioned. Removed kennels trigger
conflict detection. Auto-reassignment attempted if compatible kennel available.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


# ── These tests call the provisioning service once implemented ─────────────────
# from app.services.kennel_provisioning import (
#     provision_kennels, detect_deactivation_conflicts, auto_reassign
# )


def compute_next_kennel_number(existing_numbers: list[str]) -> str:
    """Helper: compute next sequential kennel number (K-01, K-02 ...)."""
    # This logic will live in the provisioning service.
    # Imported here once implemented: from app.services.kennel_provisioning import compute_next_kennel_number
    from app.services import kennel_provisioning  # type: ignore
    return kennel_provisioning.compute_next_kennel_number(existing_numbers)


def test_first_kennel_is_k01():
    assert compute_next_kennel_number([]) == "K-01"


def test_next_kennel_after_k01_is_k02():
    assert compute_next_kennel_number(["K-01"]) == "K-02"


def test_sequential_numbering_fills_gaps():
    """Numbers should be strictly sequential, not gap-filling."""
    result = compute_next_kennel_number(["K-01", "K-02", "K-03"])
    assert result == "K-04"


def test_kennel_number_pads_to_two_digits():
    existing = [f"K-{i:02d}" for i in range(1, 10)]
    assert compute_next_kennel_number(existing) == "K-10"


def test_natural_sort_order():
    """K-02 sorts before K-10 (natural sort, not lexicographic)."""
    numbers = ["K-01", "K-09", "K-10", "K-02"]
    # Natural sort: K-01, K-02, K-09, K-10
    from app.services import kennel_provisioning  # type: ignore
    sorted_numbers = kennel_provisioning.natural_sort_kennel_numbers(numbers)
    assert sorted_numbers == ["K-01", "K-02", "K-09", "K-10"]


def test_deactivation_blocked_with_future_reservations():
    """Cannot deactivate kennel that has future reservations — must raise."""
    from app.services import kennel_provisioning  # type: ignore
    with pytest.raises(ValueError, match="future reservations"):
        kennel_provisioning.assert_no_future_reservations(
            kennel_id="K-01",
            future_reservations=[{"reservation_id": "r1", "dropoff_datetime": "2026-05-10"}],
        )


def test_deactivation_allowed_with_no_future_reservations():
    from app.services import kennel_provisioning  # type: ignore
    # Should not raise
    kennel_provisioning.assert_no_future_reservations(kennel_id="K-01", future_reservations=[])
