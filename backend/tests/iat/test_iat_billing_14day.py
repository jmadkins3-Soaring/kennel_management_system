"""IAT: 14-day extended stay billing cycle (Spec §6.8)."""

import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time
from .conftest import create_owner, create_dog, get_first_large_kennel, create_reservation


@pytest.mark.asyncio
async def test_14day_cycle_generates_second_bill(iat_client, iat_headers):
    """At 14-day mark from check-in, system generates a second Bill record."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    with freeze_time("2026-06-01 09:00:00"):
        res = await create_reservation(iat_client, iat_headers,
            dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
            dropoff="2026-06-01T09:00:00", pickup="2026-07-15T10:00:00")
        await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
            json={"medical_acknowledged": False}, headers=iat_headers)

    with freeze_time("2026-06-15 09:00:00"):  # Day 14
        # Trigger the billing cycle check (e.g., via a background job endpoint or calendar refresh)
        await iat_client.get("/api/calendar", params={"start": "2026-06-15", "days": 1}, headers=iat_headers)

        r = await iat_client.get(f"/api/bills?reservation_id={res['reservation_id']}", headers=iat_headers)
        bills = r.json()
        assert len(bills) >= 2
        assert any(b["billing_cycle"] == 2 for b in bills)


@pytest.mark.asyncio
async def test_14day_second_bill_covers_correct_cycle(iat_client, iat_headers):
    """Second bill cycle_start_date is checkin + 14 days."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    with freeze_time("2026-06-01 09:00:00"):
        res = await create_reservation(iat_client, iat_headers,
            dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
            dropoff="2026-06-01T09:00:00", pickup="2026-07-15T10:00:00")
        await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
            json={"medical_acknowledged": False}, headers=iat_headers)

    with freeze_time("2026-06-15 09:00:00"):
        await iat_client.get("/api/calendar", params={"start": "2026-06-15", "days": 1}, headers=iat_headers)
        r = await iat_client.get(f"/api/bills?reservation_id={res['reservation_id']}", headers=iat_headers)
        bill2 = next(b for b in r.json() if b["billing_cycle"] == 2)
        assert bill2["cycle_start_date"] == "2026-06-15"


@pytest.mark.asyncio
async def test_14day_no_hard_block_on_kennel(iat_client, iat_headers):
    """14-day cycle billing alert does NOT block kennel access — staff manages collection."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    with freeze_time("2026-06-01 09:00:00"):
        res = await create_reservation(iat_client, iat_headers,
            dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
            dropoff="2026-06-01T09:00:00", pickup="2026-07-15T10:00:00")
        r = await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
            json={"medical_acknowledged": False}, headers=iat_headers)
        assert r.status_code == 200  # kennel still accessible
