"""IAT: Pickup overdue alert detection and dismissal (Spec §6.7).

The /api/calendar/overdue endpoint returns active overdue pickups.
The /api/calendar/overdue/{id}/dismiss endpoint lets staff dismiss an alert.
"""

import pytest
from freezegun import freeze_time
from .conftest import create_owner, create_dog, get_first_large_kennel, create_reservation


@pytest.mark.asyncio
async def test_overdue_appears_after_threshold(iat_client, iat_headers):
    """Reservation 3h past its pickup_datetime appears in the overdue list."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    with freeze_time("2026-06-01 09:00:00"):
        res = await create_reservation(
            iat_client, iat_headers,
            dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
            dropoff="2026-06-01T09:00:00",
            pickup="2026-06-02T10:00:00",
        )
        await iat_client.post(
            f"/api/reservations/{res['reservation_id']}/checkin",
            json={"medical_acknowledged": False},
            headers=iat_headers,
        )

    # 1 minute past threshold (pickup 10:00 + 3h = 13:00, now = 13:01)
    with freeze_time("2026-06-02 13:01:00"):
        r = await iat_client.get("/api/calendar/overdue", headers=iat_headers)
        assert r.status_code == 200
        overdue = r.json()
        ids = [o["reservation_id"] for o in overdue]
        assert res["reservation_id"] in ids

        entry = next(o for o in overdue if o["reservation_id"] == res["reservation_id"])
        assert entry["hours_overdue"] >= 3.0
        assert entry["dismissed"] is False


@pytest.mark.asyncio
async def test_not_overdue_before_threshold(iat_client, iat_headers):
    """Reservation 2h59m past its pickup does NOT appear in the overdue list."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    with freeze_time("2026-06-01 09:00:00"):
        res = await create_reservation(
            iat_client, iat_headers,
            dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
            dropoff="2026-06-01T09:00:00",
            pickup="2026-06-02T10:00:00",
        )
        await iat_client.post(
            f"/api/reservations/{res['reservation_id']}/checkin",
            json={"medical_acknowledged": False},
            headers=iat_headers,
        )

    # 1 minute before threshold (12:59)
    with freeze_time("2026-06-02 12:59:00"):
        r = await iat_client.get("/api/calendar/overdue", headers=iat_headers)
        assert r.status_code == 200
        ids = [o["reservation_id"] for o in r.json()]
        assert res["reservation_id"] not in ids


@pytest.mark.asyncio
async def test_dismiss_sets_dismissed_flag(iat_client, iat_headers):
    """POST /overdue/{id}/dismiss sets dismissed=True on the alert."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    with freeze_time("2026-06-01 09:00:00"):
        res = await create_reservation(
            iat_client, iat_headers,
            dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
            dropoff="2026-06-01T09:00:00",
            pickup="2026-06-02T10:00:00",
        )
        await iat_client.post(
            f"/api/reservations/{res['reservation_id']}/checkin",
            json={"medical_acknowledged": False},
            headers=iat_headers,
        )

    with freeze_time("2026-06-02 14:00:00"):
        dr = await iat_client.post(
            f"/api/calendar/overdue/{res['reservation_id']}/dismiss",
            headers=iat_headers,
        )
        assert dr.status_code == 200
        assert dr.json()["dismissed"] is True

        # Entry now shows dismissed=True in overdue list
        r = await iat_client.get("/api/calendar/overdue", headers=iat_headers)
        overdue = r.json()
        entry = next((o for o in overdue if o["reservation_id"] == res["reservation_id"]), None)
        if entry:
            assert entry["dismissed"] is True


@pytest.mark.asyncio
async def test_checked_out_reservation_not_overdue(iat_client, iat_headers):
    """Checked-out reservations are never listed as overdue regardless of pickup time."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    with freeze_time("2026-06-01 09:00:00"):
        res = await create_reservation(
            iat_client, iat_headers,
            dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
            dropoff="2026-06-01T09:00:00",
            pickup="2026-06-02T10:00:00",
        )
        await iat_client.post(
            f"/api/reservations/{res['reservation_id']}/checkin",
            json={"medical_acknowledged": False},
            headers=iat_headers,
        )

    with freeze_time("2026-06-02 09:00:00"):
        await iat_client.post(
            f"/api/reservations/{res['reservation_id']}/checkout",
            json={"checkout_healthy": True},
            headers=iat_headers,
        )

    # Well past pickup time — but already checked out
    with freeze_time("2026-06-02 16:00:00"):
        r = await iat_client.get("/api/calendar/overdue", headers=iat_headers)
        ids = [o["reservation_id"] for o in r.json()]
        assert res["reservation_id"] not in ids
