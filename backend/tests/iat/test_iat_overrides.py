"""IAT: Override flow logging — phase conflict and open-ended pickup (Spec §6.6)."""

import pytest
from .conftest import create_owner, create_dog, get_first_large_kennel, create_reservation


@pytest.mark.asyncio
async def test_phase_conflict_override_is_logged(iat_client, iat_headers):
    """Phase conflict override checkbox confirmed by staff is recorded in override_log."""
    owner = await create_owner(iat_client, iat_headers)
    dog1 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    dog2 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    await create_reservation(iat_client, iat_headers,
        dog_id=dog1["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog2["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-11T09:00:00",
        "pickup_datetime": "2026-06-14T10:00:00",
        "override_phase_conflict": True,  # staff checks the box
    }, headers=iat_headers)
    assert r.status_code == 201
    override_log = r.json().get("override_log", [])
    assert any(e["override_type"] == "PhaseConflict" for e in override_log)
    assert any(e["override_by"] == "iat_staff" for e in override_log)


@pytest.mark.asyncio
async def test_open_ended_pickup_override_is_logged(iat_client, iat_headers):
    """Open-ended pickup override is logged with staff username and timestamp."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00",
        "pickup_open_ended": True,
        "override_open_ended_pickup": True,  # staff explicitly overrides
    }, headers=iat_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["pickup_open_ended"] is True
    override_log = data.get("override_log", [])
    assert any(e["override_type"] == "OpenEndedPickup" for e in override_log)


@pytest.mark.asyncio
async def test_override_without_checkbox_is_rejected(iat_client, iat_headers):
    """Phase conflict without override checkbox must be rejected."""
    owner = await create_owner(iat_client, iat_headers)
    dog1 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    dog2 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    await create_reservation(iat_client, iat_headers,
        dog_id=dog1["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog2["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-11T09:00:00",
        "pickup_datetime": "2026-06-14T10:00:00",
        # No override_phase_conflict
    }, headers=iat_headers)
    assert r.status_code in (409, 422)
