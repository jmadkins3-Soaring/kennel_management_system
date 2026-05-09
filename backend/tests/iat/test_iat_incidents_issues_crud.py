"""IAT: Incident and Issue CRUD endpoints not covered by lifecycle tests."""

import pytest
from .conftest import create_owner, create_dog, create_reservation, get_first_large_kennel


async def _make_reservation_with_checkin(client, headers) -> tuple:
    owner = await create_owner(client, headers)
    dog = await create_dog(client, headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(client, headers)
    res = await create_reservation(client, headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")
    await client.post(f"/api/reservations/{res['reservation_id']}/checkin",
        json={"medical_acknowledged": False}, headers=headers)
    return dog, kennel, res


# ── Incident endpoints ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_incidents_empty(iat_client, iat_headers):
    r = await iat_client.get("/api/incidents", headers=iat_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_get_incident_by_id(iat_client, iat_headers):
    dog, _, res = await _make_reservation_with_checkin(iat_client, iat_headers)
    r = await iat_client.post("/api/incidents", json={
        "dog_id": dog["dog_id"],
        "reservation_id": res["reservation_id"],
        "incident_type": "Behavioral",
        "description": "Bit another dog.",
        "occurred_datetime": "2026-06-10T12:00:00",
    }, headers=iat_headers)
    assert r.status_code == 201
    inc_id = r.json()["incident_id"]

    r2 = await iat_client.get(f"/api/incidents/{inc_id}", headers=iat_headers)
    assert r2.status_code == 200
    assert r2.json()["incident_id"] == inc_id


@pytest.mark.asyncio
async def test_get_incident_not_found(iat_client, iat_headers):
    r = await iat_client.get("/api/incidents/no-such-id", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_incidents_filter_by_dog(iat_client, iat_headers):
    dog, _, res = await _make_reservation_with_checkin(iat_client, iat_headers)
    await iat_client.post("/api/incidents", json={
        "dog_id": dog["dog_id"],
        "reservation_id": res["reservation_id"],
        "incident_type": "Medical",
        "description": "Limping.",
        "occurred_datetime": "2026-06-11T10:00:00",
    }, headers=iat_headers)

    r = await iat_client.get(f"/api/incidents?dog_id={dog['dog_id']}", headers=iat_headers)
    assert r.status_code == 200
    assert all(i["dog_id"] == dog["dog_id"] for i in r.json())


@pytest.mark.asyncio
async def test_list_incidents_filter_by_resolved(iat_client, iat_headers):
    dog, _, res = await _make_reservation_with_checkin(iat_client, iat_headers)
    cr = await iat_client.post("/api/incidents", json={
        "dog_id": dog["dog_id"],
        "reservation_id": res["reservation_id"],
        "incident_type": "Behavioral",
        "description": "Growled.",
        "occurred_datetime": "2026-06-10T11:00:00",
    }, headers=iat_headers)
    inc_id = cr.json()["incident_id"]
    await iat_client.post(f"/api/incidents/{inc_id}/resolve",
                          json={"notes": "Monitored, no further issues."}, headers=iat_headers)

    r = await iat_client.get("/api/incidents?resolved=true", headers=iat_headers)
    assert r.status_code == 200
    assert all(i["resolved"] for i in r.json())

    r2 = await iat_client.get("/api/incidents?resolved=false", headers=iat_headers)
    assert r2.status_code == 200
    assert all(not i["resolved"] for i in r2.json())


@pytest.mark.asyncio
async def test_resolve_incident(iat_client, iat_headers):
    dog, _, res = await _make_reservation_with_checkin(iat_client, iat_headers)
    cr = await iat_client.post("/api/incidents", json={
        "dog_id": dog["dog_id"],
        "reservation_id": res["reservation_id"],
        "incident_type": "Medical",
        "description": "Minor cut on paw.",
        "occurred_datetime": "2026-06-11T09:00:00",
    }, headers=iat_headers)
    inc_id = cr.json()["incident_id"]

    r = await iat_client.post(f"/api/incidents/{inc_id}/resolve",
                              json={"notes": "Cleaned and bandaged."}, headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["resolved"] is True
    assert data["resolved_by"] == "iat_staff"
    assert data["resolved_datetime"] is not None


@pytest.mark.asyncio
async def test_resolve_incident_not_found(iat_client, iat_headers):
    r = await iat_client.post("/api/incidents/no-such-id/resolve",
                              json={"notes": "N/A"}, headers=iat_headers)
    assert r.status_code == 404


# ── Issue endpoints ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_issues_empty(iat_client, iat_headers):
    r = await iat_client.get("/api/issues", headers=iat_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_and_get_issue(iat_client, iat_headers):
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    r = await iat_client.post("/api/issues", json={
        "kennel_id": kennel["kennel_id"],
        "issue_type": "Maintenance",
        "description": "Latch broken.",
        "reported_datetime": "2026-06-10T08:00:00",
    }, headers=iat_headers)
    assert r.status_code == 201
    issue_id = r.json()["issue_id"]

    r2 = await iat_client.get(f"/api/issues/{issue_id}", headers=iat_headers)
    assert r2.status_code == 200
    assert r2.json()["issue_id"] == issue_id


@pytest.mark.asyncio
async def test_get_issue_not_found(iat_client, iat_headers):
    r = await iat_client.get("/api/issues/no-such-id", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_issues_filter_by_kennel(iat_client, iat_headers):
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    await iat_client.post("/api/issues", json={
        "kennel_id": kennel["kennel_id"],
        "issue_type": "Sanitation",
        "description": "Drain clogged.",
        "reported_datetime": "2026-06-10T07:00:00",
    }, headers=iat_headers)

    r = await iat_client.get(f"/api/issues?kennel_id={kennel['kennel_id']}", headers=iat_headers)
    assert r.status_code == 200
    assert all(i["kennel_id"] == kennel["kennel_id"] for i in r.json())


@pytest.mark.asyncio
async def test_list_issues_filter_by_resolved(iat_client, iat_headers):
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    cr = await iat_client.post("/api/issues", json={
        "kennel_id": kennel["kennel_id"],
        "issue_type": "Safety",
        "description": "Loose wire.",
        "reported_datetime": "2026-06-10T07:30:00",
    }, headers=iat_headers)
    issue_id = cr.json()["issue_id"]
    await iat_client.post(f"/api/issues/{issue_id}/resolve",
                          json={"notes": "Wire secured."}, headers=iat_headers)

    r = await iat_client.get("/api/issues?resolved=true", headers=iat_headers)
    assert r.status_code == 200
    assert all(i["resolved"] for i in r.json())

    r2 = await iat_client.get("/api/issues?resolved=false", headers=iat_headers)
    assert r2.status_code == 200
    assert all(not i["resolved"] for i in r2.json())


@pytest.mark.asyncio
async def test_resolve_issue(iat_client, iat_headers):
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    cr = await iat_client.post("/api/issues", json={
        "kennel_id": kennel["kennel_id"],
        "issue_type": "Maintenance",
        "description": "Door squeaks.",
        "reported_datetime": "2026-06-11T07:00:00",
    }, headers=iat_headers)
    issue_id = cr.json()["issue_id"]

    r = await iat_client.post(f"/api/issues/{issue_id}/resolve",
                              json={"notes": "Hinges oiled."}, headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["resolved"] is True
    assert data["resolved_by"] == "iat_staff"
    assert data["resolved_datetime"] is not None


@pytest.mark.asyncio
async def test_resolve_issue_not_found(iat_client, iat_headers):
    r = await iat_client.post("/api/issues/no-such-id/resolve",
                              json={"notes": "N/A"}, headers=iat_headers)
    assert r.status_code == 404
