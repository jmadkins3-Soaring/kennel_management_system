"""IAT: Calendar grid, day view, overdue pickups, dismiss."""

import pytest
from freezegun import freeze_time
from .conftest import create_owner, create_dog, create_reservation, get_first_large_kennel


@pytest.mark.asyncio
async def test_calendar_grid_empty(iat_client, iat_headers):
    r = await iat_client.get("/api/calendar?start=2026-06-10&days=3", headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert "kennels" in data
    assert data["start_date"] == "2026-06-10"
    assert data["days"] == 3
    assert "overdue_pickups" in data
    assert "alerts" in data


@pytest.mark.asyncio
async def test_calendar_grid_shows_assigned_kennel(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    r = await iat_client.get("/api/calendar?start=2026-06-10&days=2", headers=iat_headers)
    assert r.status_code == 200
    found_assigned = False
    for k_row in r.json()["kennels"]:
        if k_row["kennel_id"] == kennel["kennel_id"]:
            for day in k_row["days"]:
                for phase, cell in day["phases"].items():
                    if cell["status"] in ("Assigned", "Used"):
                        found_assigned = True
    assert found_assigned


@pytest.mark.asyncio
async def test_calendar_grid_default_days(iat_client, iat_headers):
    r = await iat_client.get("/api/calendar?start=2026-06-01", headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["days"] == 10


@pytest.mark.asyncio
async def test_calendar_day_view_returns_flat_cells(iat_client, iat_headers):
    r = await iat_client.get("/api/calendar/day/2026-06-10", headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # 4 phases × N kennels
    assert len(data) == 4 * 4  # 4 seeded kennels × 4 phases
    assert all("phase" in cell for cell in data)
    assert all("status" in cell for cell in data)


@pytest.mark.asyncio
async def test_calendar_day_view_with_checkin(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
                          json={"medical_acknowledged": False}, headers=iat_headers)

    r = await iat_client.get("/api/calendar/day/2026-06-10", headers=iat_headers)
    assert r.status_code == 200
    cells = [c for c in r.json() if c["kennel_id"] == kennel["kennel_id"]]
    statuses = {c["phase"]: c["status"] for c in cells}
    # Morning phase (checkin at 09:00 = Morning) should be Used
    assert "Used" in statuses.values()


@pytest.mark.asyncio
async def test_overdue_pickups_empty(iat_client, iat_headers):
    r = await iat_client.get("/api/calendar/overdue", headers=iat_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_overdue_pickups_shows_past_due(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    # Checkin in the past so pickup is overdue
    with freeze_time("2026-05-01T09:00:00"):
        res = await create_reservation(iat_client, iat_headers,
            dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
            dropoff="2026-05-01T09:00:00", pickup="2026-05-02T10:00:00")
        await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
                              json={"medical_acknowledged": False}, headers=iat_headers)

    r = await iat_client.get("/api/calendar/overdue", headers=iat_headers)
    assert r.status_code == 200
    overdue = r.json()
    assert any(o["reservation_id"] == res["reservation_id"] for o in overdue)


@pytest.mark.asyncio
async def test_dismiss_overdue_alert(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    with freeze_time("2026-05-01T09:00:00"):
        res = await create_reservation(iat_client, iat_headers,
            dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
            dropoff="2026-05-01T09:00:00", pickup="2026-05-02T10:00:00")
        await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
                              json={"medical_acknowledged": False}, headers=iat_headers)

    r = await iat_client.post(
        f"/api/calendar/overdue/{res['reservation_id']}/dismiss", headers=iat_headers
    )
    assert r.status_code == 200
    assert r.json()["dismissed"] is True


@pytest.mark.asyncio
async def test_dismiss_overdue_not_found(iat_client, iat_headers):
    r = await iat_client.post("/api/calendar/overdue/no-such-id/dismiss", headers=iat_headers)
    assert r.status_code == 404
