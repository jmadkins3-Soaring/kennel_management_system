"""Unit tests: medical acknowledgment requirement at check-in.

Spec §7.2 step 7 — If dog.medical_status != Healthy, staff must check
acknowledgment box before check-in can proceed.
"""

import pytest


def requires_medical_ack(medical_status: str) -> bool:
    """
    Return True if check-in requires medical acknowledgment.
    Implemented in the check-in service/route; replicated here for unit testing.
    Once implemented, import directly:
      from app.services.checkin import requires_medical_ack
    """
    from app.services import checkin  # type: ignore
    return checkin.requires_medical_ack(medical_status)


@pytest.mark.parametrize("status,requires_ack", [
    ("Healthy",       False),
    ("Injured",       True),
    ("Quarantine",    True),
    ("On Medication", True),
    ("Other",         True),
])
def test_medical_ack_requirement(status, requires_ack):
    assert requires_medical_ack(status) == requires_ack


def test_healthy_dog_does_not_require_ack():
    assert requires_medical_ack("Healthy") is False


def test_all_non_healthy_statuses_require_ack():
    non_healthy = ["Injured", "Quarantine", "On Medication", "Other"]
    for status in non_healthy:
        assert requires_medical_ack(status) is True


def test_invalid_status_raises():
    with pytest.raises((ValueError, KeyError)):
        requires_medical_ack("Unknown Status")
