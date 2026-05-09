"""IAT: Reservation CRUD — get, update, cancel, list filters."""

import pytest
from .conftest import create_owner, create_dog, create_reservation, get_first_large_kennel


async def _basic_reservation(client, headers, dropoff="2026-06-10T09:00:00",
                               pickup="2026-06-13T10:00:00"):
    owner = await create_owner(client, headers)
    dog = await create_dog(client, headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(client, headers)
    res = await create_reservation(client, headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff=dropoff, pickup=pickup)
    return owner, dog, kennel, res


@pytest.mark.asyncio
async def test_get_reservation_by_id(iat_client, iat_headers):
    _, _, _, res = await _basic_reservation(iat_client, iat_headers)
    r = await iat_client.get(f"/api/reservations/{res['reservation_id']}", headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["reservation_id"] == res["reservation_id"]
    assert "dropoff_phase" in r.json()


@pytest.mark.asyncio
async def test_get_reservation_not_found(iat_client, iat_headers):
    r = await iat_client.get("/api/reservations/no-such-id", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_reservations_by_dog_id(iat_client, iat_headers):
    _, dog, _, res = await _basic_reservation(iat_client, iat_headers)
    r = await iat_client.get(f"/api/reservations?dog_id={dog['dog_id']}", headers=iat_headers)
    assert r.status_code == 200
    assert all(rv["dog_id"] == dog["dog_id"] for rv in r.json())


@pytest.mark.asyncio
async def test_list_reservations_by_owner_id(iat_client, iat_headers):
    owner, dog, kennel, _ = await _basic_reservation(iat_client, iat_headers)
    r = await iat_client.get(
        f"/api/reservations?owner_id={owner['owner_id']}", headers=iat_headers
    )
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_list_reservations_by_kennel_id(iat_client, iat_headers):
    _, _, kennel, _ = await _basic_reservation(iat_client, iat_headers)
    r = await iat_client.get(
        f"/api/reservations?kennel_id={kennel['kennel_id']}", headers=iat_headers
    )
    assert r.status_code == 200
    assert all(rv["kennel_id"] == kennel["kennel_id"] for rv in r.json())


@pytest.mark.asyncio
async def test_list_reservations_by_date_range(iat_client, iat_headers):
    await _basic_reservation(iat_client, iat_headers,
                              dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")
    r = await iat_client.get(
        "/api/reservations?start_date=2026-06-09&end_date=2026-06-11", headers=iat_headers
    )
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_update_reservation_change_pickup(iat_client, iat_headers):
    _, _, _, res = await _basic_reservation(iat_client, iat_headers)
    r = await iat_client.put(f"/api/reservations/{res['reservation_id']}",
                             json={"pickup_datetime": "2026-06-15T10:00:00"},
                             headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["pickup_datetime"].startswith("2026-06-15")


@pytest.mark.asyncio
async def test_update_reservation_not_found(iat_client, iat_headers):
    r = await iat_client.put("/api/reservations/no-such-id",
                             json={"notes": "x"}, headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_reservation_blocked_after_checkin(iat_client, iat_headers):
    _, _, _, res = await _basic_reservation(iat_client, iat_headers)
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
                          json={"medical_acknowledged": False}, headers=iat_headers)
    r = await iat_client.put(f"/api/reservations/{res['reservation_id']}",
                             json={"notes": "changed"}, headers=iat_headers)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_update_reservation_invalid_kennel(iat_client, iat_headers):
    _, _, _, res = await _basic_reservation(iat_client, iat_headers)
    r = await iat_client.put(f"/api/reservations/{res['reservation_id']}",
                             json={"kennel_id": "no-such-kennel"}, headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_cancel_reservation_staff(iat_client, iat_headers):
    _, _, _, res = await _basic_reservation(iat_client, iat_headers)
    r = await iat_client.post(
        f"/api/reservations/{res['reservation_id']}/cancel?requested_by=Staff",
        headers=iat_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["cancelled"] is True
    assert data["cancel_confirmed_by"] == "iat_staff"


@pytest.mark.asyncio
async def test_cancel_reservation_owner_request(iat_client, iat_headers):
    """Owner-initiated cancel: records request but does NOT set cancelled=True."""
    _, _, _, res = await _basic_reservation(iat_client, iat_headers)
    r = await iat_client.post(
        f"/api/reservations/{res['reservation_id']}/cancel?requested_by=Owner",
        headers=iat_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["cancelled"] is False
    assert data["cancel_requested_by"] == "Owner"
    assert data["cancel_confirmed_by"] is None


@pytest.mark.asyncio
async def test_cancel_reservation_not_found(iat_client, iat_headers):
    r = await iat_client.post("/api/reservations/no-such-id/cancel", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_cancelled_reservations(iat_client, iat_headers):
    _, _, _, res = await _basic_reservation(iat_client, iat_headers)
    await iat_client.post(
        f"/api/reservations/{res['reservation_id']}/cancel", headers=iat_headers
    )
    r = await iat_client.get("/api/reservations?cancelled=true", headers=iat_headers)
    assert r.status_code == 200
    assert all(rv["cancelled"] for rv in r.json())
