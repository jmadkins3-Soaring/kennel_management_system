"""IAT: Kennel CRUD, holds, status computation, issue listing."""

import pytest
from .conftest import (
    create_owner, create_dog, create_reservation, get_first_large_kennel,
)


@pytest.mark.asyncio
async def test_list_kennels(iat_client, iat_headers):
    r = await iat_client.get("/api/kennels", headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert all("current_status" in k for k in data)


@pytest.mark.asyncio
async def test_list_kennels_for_date(iat_client, iat_headers):
    r = await iat_client.get("/api/kennels?for_date=2026-06-10", headers=iat_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_list_kennels_for_date_and_phase(iat_client, iat_headers):
    r = await iat_client.get(
        "/api/kennels?for_date=2026-06-10&for_phase=Morning", headers=iat_headers
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_kennel_by_id(iat_client, iat_headers):
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    r = await iat_client.get(f"/api/kennels/{kennel['kennel_id']}", headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["kennel_id"] == kennel["kennel_id"]
    assert "current_status" in r.json()


@pytest.mark.asyncio
async def test_get_kennel_not_found(iat_client, iat_headers):
    r = await iat_client.get("/api/kennels/no-such-id", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_kennel_description(iat_client, iat_headers):
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    r = await iat_client.put(
        f"/api/kennels/{kennel['kennel_id']}",
        json={"description": "Freshly cleaned"},
        headers=iat_headers,
    )
    assert r.status_code == 200
    assert r.json()["description"] == "Freshly cleaned"


@pytest.mark.asyncio
async def test_deactivate_kennel_with_no_future_reservations(iat_client, iat_headers):
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    r = await iat_client.put(
        f"/api/kennels/{kennel['kennel_id']}",
        json={"active": False},
        headers=iat_headers,
    )
    assert r.status_code == 200
    assert r.json()["active"] is False


@pytest.mark.asyncio
async def test_deactivate_kennel_blocked_with_future_reservation(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    await create_reservation(
        iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-07-01T09:00:00", pickup="2026-07-05T10:00:00",
    )
    r = await iat_client.put(
        f"/api/kennels/{kennel['kennel_id']}",
        json={"active": False},
        headers=iat_headers,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_update_kennel_not_found(iat_client, iat_headers):
    r = await iat_client.put("/api/kennels/no-such-id", json={"notes": "x"}, headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_place_and_lift_hold(iat_client, iat_headers):
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    r = await iat_client.post(
        f"/api/kennels/{kennel['kennel_id']}/holds",
        json={
            "kennel_id": kennel["kennel_id"],
            "start_date": "2026-06-20",
            "end_date": "2026-06-22",
            "reason": "Deep cleaning",
        },
        headers=iat_headers,
    )
    assert r.status_code == 201
    hold_id = r.json()["hold_id"]
    assert r.json()["active"] is True

    # Kennel should show as Hold for that date
    r2 = await iat_client.get(
        f"/api/kennels?for_date=2026-06-21", headers=iat_headers
    )
    statuses = {k["kennel_id"]: k["current_status"] for k in r2.json()}
    assert statuses.get(kennel["kennel_id"]) == "Hold"

    # Lift the hold
    r3 = await iat_client.delete(
        f"/api/kennels/{kennel['kennel_id']}/holds/{hold_id}", headers=iat_headers
    )
    assert r3.status_code == 204


@pytest.mark.asyncio
async def test_place_hold_kennel_not_found(iat_client, iat_headers):
    r = await iat_client.post(
        "/api/kennels/no-such-id/holds",
        json={
            "kennel_id": "no-such-id",
            "start_date": "2026-06-20",
            "end_date": "2026-06-22",
        },
        headers=iat_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_lift_hold_not_found(iat_client, iat_headers):
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    r = await iat_client.delete(
        f"/api/kennels/{kennel['kennel_id']}/holds/no-such-hold", headers=iat_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_kennel_issues_empty(iat_client, iat_headers):
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    r = await iat_client.get(f"/api/kennels/{kennel['kennel_id']}/issues", headers=iat_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_kennel_issues_with_open_issue(iat_client, iat_headers):
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    await iat_client.post("/api/issues", json={
        "kennel_id": kennel["kennel_id"],
        "issue_type": "Maintenance",
        "description": "Latch loose.",
        "reported_datetime": "2026-06-01T08:00:00",
    }, headers=iat_headers)

    r = await iat_client.get(f"/api/kennels/{kennel['kennel_id']}/issues", headers=iat_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_list_kennel_issues_not_found(iat_client, iat_headers):
    r = await iat_client.get("/api/kennels/no-such-id/issues", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_kennel_status_used_when_checked_in(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(
        iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00",
    )
    await iat_client.post(
        f"/api/reservations/{res['reservation_id']}/checkin",
        json={"medical_acknowledged": False},
        headers=iat_headers,
    )
    r = await iat_client.get(f"/api/kennels/{kennel['kennel_id']}", headers=iat_headers)
    assert r.json()["current_status"] == "Used"
