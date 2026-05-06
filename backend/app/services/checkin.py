"""Check-in business rules extracted as pure functions for unit testability."""

HEALTHY_STATUS = "Healthy"
VALID_STATUSES = {"Healthy", "Injured", "Quarantine", "On Medication", "Other"}


def requires_medical_ack(medical_status: str) -> bool:
    """Return True if check-in requires medical acknowledgment (status is not Healthy)."""
    if medical_status not in VALID_STATUSES:
        raise ValueError(f"Unknown medical status: {medical_status!r}")
    return medical_status != HEALTHY_STATUS
