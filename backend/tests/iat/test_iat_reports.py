"""IAT: Report endpoints — assert 200 + PDF content-type for all five reports."""

import pytest
from .conftest import create_owner, create_dog, create_reservation, get_first_large_kennel


async def _seed_active_stay(client, headers):
    owner = await create_owner(client, headers)
    dog = await create_dog(client, headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(client, headers)
    res = await create_reservation(client, headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")
    await client.post(f"/api/reservations/{res['reservation_id']}/checkin",
                      json={"medical_acknowledged": False}, headers=headers)
    return res


# ── PACFA Compliance ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_pacfa_empty_db(iat_client, iat_headers):
    r = await iat_client.get("/api/reports/pacfa", headers=iat_headers)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")


@pytest.mark.asyncio
async def test_report_pacfa_with_active_stay(iat_client, iat_headers):
    await _seed_active_stay(iat_client, iat_headers)
    r = await iat_client.get("/api/reports/pacfa", headers=iat_headers)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")


# ── Occupancy ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_occupancy_required_params(iat_client, iat_headers):
    r = await iat_client.get(
        "/api/reports/occupancy?start_date=2026-06-01&end_date=2026-06-30",
        headers=iat_headers,
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")


@pytest.mark.asyncio
async def test_report_occupancy_with_date_range(iat_client, iat_headers):
    await _seed_active_stay(iat_client, iat_headers)
    r = await iat_client.get(
        "/api/reports/occupancy?start_date=2026-06-01&end_date=2026-06-30",
        headers=iat_headers,
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")


# ── Revenue ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_revenue_required_params(iat_client, iat_headers):
    r = await iat_client.get(
        "/api/reports/revenue?start_date=2026-06-01&end_date=2026-06-30",
        headers=iat_headers,
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")


@pytest.mark.asyncio
async def test_report_revenue_with_date_range(iat_client, iat_headers):
    r = await iat_client.get(
        "/api/reports/revenue?start_date=2026-06-01&end_date=2026-06-30",
        headers=iat_headers,
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")


# ── Upcoming ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_upcoming_no_params(iat_client, iat_headers):
    r = await iat_client.get("/api/reports/upcoming", headers=iat_headers)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")


@pytest.mark.asyncio
async def test_report_upcoming_with_days(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")
    r = await iat_client.get("/api/reports/upcoming?days=30", headers=iat_headers)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")


# ── Open Incidents ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_open_incidents_empty(iat_client, iat_headers):
    r = await iat_client.get("/api/reports/open-incidents", headers=iat_headers)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")


@pytest.mark.asyncio
async def test_report_open_incidents_with_data(iat_client, iat_headers):
    res = await _seed_active_stay(iat_client, iat_headers)
    dog_r = await iat_client.get(
        f"/api/reservations/{res['reservation_id']}", headers=iat_headers
    )
    dog_id = dog_r.json()["dog_id"]

    await iat_client.post("/api/incidents", json={
        "dog_id": dog_id,
        "reservation_id": res["reservation_id"],
        "incident_type": "Behavioral",
        "description": "Test incident.",
        "occurred_datetime": "2026-06-10T11:00:00",
    }, headers=iat_headers)

    kennel = await get_first_large_kennel(iat_client, iat_headers)
    await iat_client.post("/api/issues", json={
        "kennel_id": kennel["kennel_id"],
        "issue_type": "Maintenance",
        "description": "Broken latch.",
        "reported_datetime": "2026-06-10T08:00:00",
    }, headers=iat_headers)

    r = await iat_client.get("/api/reports/open-incidents", headers=iat_headers)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
