"""IAT: Cancellation flow (Spec §7.4)."""

import pytest
from .conftest import create_owner, create_dog, get_first_large_kennel, create_reservation


@pytest.mark.asyncio
async def test_staff_cancel_reservation(iat_client, iat_headers):
    """Staff cancels reservation. cancelled=True, cancel_confirmed_by set."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    r = await iat_client.post(
        f"/api/reservations/{res['reservation_id']}/cancel",
        params={"requested_by": "Staff"},
        headers=iat_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["cancelled"] is True
    assert data["cancel_confirmed_by"] == "iat_staff"


@pytest.mark.asyncio
async def test_cancel_releases_kennel_phases(iat_client, iat_headers):
    """After cancellation, kennel phase becomes Free for previously blocked dates."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    await iat_client.post(f"/api/reservations/{res['reservation_id']}/cancel",
        params={"requested_by": "Staff"}, headers=iat_headers)

    r = await iat_client.get("/api/calendar/day/2026-06-11", headers=iat_headers)
    cells = r.json()
    kennel_cells = [c for c in cells if c["kennel_id"] == kennel["kennel_id"]]
    for cell in kennel_cells:
        assert cell["status"] == "Free"


@pytest.mark.asyncio
async def test_owner_cancel_request_requires_staff_confirmation(iat_client, iat_headers):
    """Owner-initiated cancel sets cancel_requested_by=Owner but does NOT set cancelled=True yet."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    # Owner submits cancellation request via portal
    r = await iat_client.post(
        f"/api/reservations/{res['reservation_id']}/cancel",
        params={"requested_by": "Owner"},
        headers=iat_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["cancel_requested_by"] == "Owner"
    # Not fully cancelled until staff confirms
    assert data["cancelled"] is False
    assert data["cancel_confirmed_by"] is None
