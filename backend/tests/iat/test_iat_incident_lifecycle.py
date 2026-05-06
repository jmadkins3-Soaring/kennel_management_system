"""IAT: Incident report lifecycle (Spec §7.5)."""

import pytest
from .conftest import create_owner, create_dog, get_first_large_kennel, create_reservation


@pytest.mark.asyncio
async def test_create_incident_report(iat_client, iat_headers):
    """Incident created with all required fields. reported_by set from JWT."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    r = await iat_client.post("/api/incidents", json={
        "dog_id": dog["dog_id"],
        "reservation_id": res["reservation_id"],
        "incident_type": "Behavioral",
        "description": "Dog showed aggression at feeding time.",
        "occurred_datetime": "2026-06-11T08:00:00",
        "visible_to_owner": False,
    }, headers=iat_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["reported_by"] == "iat_staff"
    assert data["resolved"] is False


@pytest.mark.asyncio
async def test_open_incident_sets_dog_open_incidents_flag(iat_client, iat_headers):
    """After incident created, GET /dogs/{id} must return open_incidents=True."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    await iat_client.post("/api/incidents", json={
        "dog_id": dog["dog_id"], "reservation_id": res["reservation_id"],
        "incident_type": "Injury", "description": "Sprained paw.",
        "occurred_datetime": "2026-06-11T08:00:00",
    }, headers=iat_headers)

    r = await iat_client.get(f"/api/dogs/{dog['dog_id']}", headers=iat_headers)
    assert r.json()["open_incidents"] is True


@pytest.mark.asyncio
async def test_open_incident_blocks_same_dog_checkin(iat_client, iat_headers):
    """Dog with unresolved incident cannot be checked in again — hard block."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-12T10:00:00")

    incident_r = await iat_client.post("/api/incidents", json={
        "dog_id": dog["dog_id"], "reservation_id": res["reservation_id"],
        "incident_type": "Behavioral", "description": "Aggression.",
        "occurred_datetime": "2026-06-11T08:00:00",
    }, headers=iat_headers)

    res2 = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-14T09:00:00", pickup="2026-06-16T10:00:00")

    r = await iat_client.post(f"/api/reservations/{res2['reservation_id']}/checkin",
        json={"medical_acknowledged": False}, headers=iat_headers)
    assert r.status_code in (409, 422)


@pytest.mark.asyncio
async def test_resolve_incident_unblocks_checkin(iat_client, iat_headers):
    """Resolving incident allows same dog to check in again."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-12T10:00:00")

    ir = await iat_client.post("/api/incidents", json={
        "dog_id": dog["dog_id"], "reservation_id": res["reservation_id"],
        "incident_type": "Behavioral", "description": "Aggression.",
        "occurred_datetime": "2026-06-11T08:00:00",
    }, headers=iat_headers)
    incident_id = ir.json()["incident_id"]

    await iat_client.post(f"/api/incidents/{incident_id}/resolve",
        json={"resolution_notes": "Dog assessed by vet, cleared for future stays."},
        headers=iat_headers)

    res2 = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-14T09:00:00", pickup="2026-06-16T10:00:00")

    r = await iat_client.post(f"/api/reservations/{res2['reservation_id']}/checkin",
        json={"medical_acknowledged": False}, headers=iat_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_resolve_incident_sets_resolved_fields(iat_client, iat_headers):
    """Resolved incident records resolved_datetime and resolved_by."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-12T10:00:00")

    ir = await iat_client.post("/api/incidents", json={
        "dog_id": dog["dog_id"], "reservation_id": res["reservation_id"],
        "incident_type": "Injury", "description": "Paw injury.",
        "occurred_datetime": "2026-06-11T08:00:00",
    }, headers=iat_headers)
    incident_id = ir.json()["incident_id"]

    r = await iat_client.post(f"/api/incidents/{incident_id}/resolve",
        json={"resolution_notes": "Healed."}, headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["resolved"] is True
    assert data["resolved_by"] == "iat_staff"
    assert data["resolved_datetime"] is not None
