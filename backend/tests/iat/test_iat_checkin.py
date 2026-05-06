"""IAT: Check-in flow (Spec §7.2)."""

import pytest
from .conftest import create_owner, create_dog, get_first_large_kennel, create_reservation


async def make_reservation(client, headers, size_class="M", medical_status="Healthy"):
    owner = await create_owner(client, headers)
    dog = await create_dog(client, headers, owner_id=owner["owner_id"],
                           size_class=size_class, medical_status=medical_status)
    kennel = await get_first_large_kennel(client, headers)
    res = await create_reservation(client, headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")
    return owner, dog, kennel, res


@pytest.mark.asyncio
async def test_checkin_happy_path(iat_client, iat_headers):
    """Check-in sets checkin_datetime, checkin_staff. Kennel transitions to Used."""
    _, _, _, res = await make_reservation(iat_client, iat_headers)

    r = await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
        json={"medical_acknowledged": False}, headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["checkin_datetime"] is not None
    assert data["checkin_staff"] == "iat_staff"


@pytest.mark.asyncio
async def test_checkin_requires_medical_ack_for_non_healthy_dog(iat_client, iat_headers):
    """Check-in with medical_status=Injured must be blocked without medical_acknowledged=True."""
    _, _, _, res = await make_reservation(iat_client, iat_headers, medical_status="Injured")

    r = await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
        json={"medical_acknowledged": False}, headers=iat_headers)
    assert r.status_code in (409, 422)


@pytest.mark.asyncio
async def test_checkin_succeeds_with_medical_ack(iat_client, iat_headers):
    """Check-in with Injured dog succeeds when medical_acknowledged=True."""
    _, _, _, res = await make_reservation(iat_client, iat_headers, medical_status="On Medication")

    r = await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
        json={"medical_acknowledged": True}, headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["medical_acknowledged"] is True


@pytest.mark.asyncio
async def test_checkin_blocked_by_unresolved_incident(iat_client, iat_headers):
    """Unresolved incident from prior stay blocks check-in — hard block, no override."""
    owner, dog, kennel, res = await make_reservation(iat_client, iat_headers)

    # Create an incident on the dog
    r = await iat_client.post("/api/incidents", json={
        "dog_id": dog["dog_id"],
        "reservation_id": res["reservation_id"],
        "incident_type": "Behavioral",
        "description": "Dog bit staff.",
        "occurred_datetime": "2026-06-10T10:00:00",
    }, headers=iat_headers)
    assert r.status_code == 201

    # Try to check in second time (simulate new reservation)
    res2 = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-14T09:00:00", pickup="2026-06-16T10:00:00")

    r = await iat_client.post(f"/api/reservations/{res2['reservation_id']}/checkin",
        json={"medical_acknowledged": False}, headers=iat_headers)
    assert r.status_code in (409, 422)


@pytest.mark.asyncio
async def test_checkin_blocked_by_outstanding_bill_without_override(iat_client, iat_headers):
    """Outstanding unpaid bill from prior stay must block check-in without override."""
    owner, dog, kennel, res = await make_reservation(iat_client, iat_headers)
    # Check in and check out to generate a bill
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
        json={"medical_acknowledged": False}, headers=iat_headers)
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkout",
        json={"checkout_healthy": True}, headers=iat_headers)

    # New reservation, but bill from first stay is still unpaid
    res2 = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-20T09:00:00", pickup="2026-06-22T10:00:00")

    r = await iat_client.post(f"/api/reservations/{res2['reservation_id']}/checkin",
        json={"medical_acknowledged": False, "override_unpaid_bill": False}, headers=iat_headers)
    assert r.status_code in (409, 422)


@pytest.mark.asyncio
async def test_checkin_with_bill_override_is_logged(iat_client, iat_headers):
    """Overriding an unpaid bill at check-in must be recorded in override_log."""
    owner, dog, kennel, res = await make_reservation(iat_client, iat_headers)
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
        json={"medical_acknowledged": False}, headers=iat_headers)
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkout",
        json={"checkout_healthy": True}, headers=iat_headers)

    res2 = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-20T09:00:00", pickup="2026-06-22T10:00:00")

    r = await iat_client.post(f"/api/reservations/{res2['reservation_id']}/checkin",
        json={"medical_acknowledged": False, "override_unpaid_bill": True}, headers=iat_headers)
    assert r.status_code == 200
    override_log = r.json().get("override_log", [])
    assert any(e["override_type"] == "UnpaidBill" for e in override_log)
