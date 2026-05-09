"""IAT: Activity scheduling, completion, update, and delete."""

import pytest
from .conftest import create_owner, create_dog, create_reservation, get_first_large_kennel


async def _make_reservation(client, headers):
    owner = await create_owner(client, headers)
    dog = await create_dog(client, headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(client, headers)
    res = await create_reservation(
        client, headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00",
    )
    return res


async def _schedule_activity(client, headers, reservation_id, activity_type="Nature Walk",
                              scheduled_date="2026-06-11"):
    r = await client.post("/api/activities", json={
        "reservation_id": reservation_id,
        "activity_type": activity_type,
        "scheduled_date": scheduled_date,
    }, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_list_activities_empty(iat_client, iat_headers):
    r = await iat_client.get("/api/activities", headers=iat_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_activity(iat_client, iat_headers):
    res = await _make_reservation(iat_client, iat_headers)
    act = await _schedule_activity(iat_client, iat_headers, res["reservation_id"])
    assert act["activity_type"] == "Nature Walk"
    assert act["billable"] is False
    assert act["qualifies_for_pacfa_exception"] is True  # seeded type


@pytest.mark.asyncio
async def test_create_activity_unknown_type_no_pacfa(iat_client, iat_headers):
    res = await _make_reservation(iat_client, iat_headers)
    act = await _schedule_activity(iat_client, iat_headers, res["reservation_id"],
                                   activity_type="Unknown Type")
    assert act["qualifies_for_pacfa_exception"] is False


@pytest.mark.asyncio
async def test_list_activities_by_reservation(iat_client, iat_headers):
    res = await _make_reservation(iat_client, iat_headers)
    await _schedule_activity(iat_client, iat_headers, res["reservation_id"])
    r = await iat_client.get(
        f"/api/activities?reservation_id={res['reservation_id']}", headers=iat_headers
    )
    assert r.status_code == 200
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_list_activities_by_scheduled_date(iat_client, iat_headers):
    res = await _make_reservation(iat_client, iat_headers)
    await _schedule_activity(iat_client, iat_headers, res["reservation_id"],
                             scheduled_date="2026-06-11")
    await _schedule_activity(iat_client, iat_headers, res["reservation_id"],
                             scheduled_date="2026-06-12")
    r = await iat_client.get("/api/activities?scheduled_date=2026-06-11", headers=iat_headers)
    assert r.status_code == 200
    assert all(a["scheduled_date"] == "2026-06-11" for a in r.json())


@pytest.mark.asyncio
async def test_list_activities_billable_only(iat_client, iat_headers):
    res = await _make_reservation(iat_client, iat_headers)
    act = await _schedule_activity(iat_client, iat_headers, res["reservation_id"])

    # Complete to make it billable
    await iat_client.post(f"/api/activities/{act['activity_id']}/complete", json={
        "performed_datetime": "2026-06-11T10:00:00",
    }, headers=iat_headers)

    await _schedule_activity(iat_client, iat_headers, res["reservation_id"],
                             scheduled_date="2026-06-12")  # not completed

    r = await iat_client.get("/api/activities?billable_only=true", headers=iat_headers)
    assert r.status_code == 200
    assert all(a["billable"] for a in r.json())


@pytest.mark.asyncio
async def test_update_activity_scheduled_date(iat_client, iat_headers):
    res = await _make_reservation(iat_client, iat_headers)
    act = await _schedule_activity(iat_client, iat_headers, res["reservation_id"])
    r = await iat_client.put(f"/api/activities/{act['activity_id']}",
                             json={"scheduled_date": "2026-06-12"}, headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["scheduled_date"] == "2026-06-12"


@pytest.mark.asyncio
async def test_update_activity_not_found(iat_client, iat_headers):
    r = await iat_client.put("/api/activities/no-such-id",
                             json={"scheduled_date": "2026-06-12"}, headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_performed_activity_blocked(iat_client, iat_headers):
    res = await _make_reservation(iat_client, iat_headers)
    act = await _schedule_activity(iat_client, iat_headers, res["reservation_id"])
    await iat_client.post(f"/api/activities/{act['activity_id']}/complete", json={
        "performed_datetime": "2026-06-11T10:00:00",
    }, headers=iat_headers)
    r = await iat_client.put(f"/api/activities/{act['activity_id']}",
                             json={"scheduled_date": "2026-06-13"}, headers=iat_headers)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_complete_activity(iat_client, iat_headers):
    res = await _make_reservation(iat_client, iat_headers)
    act = await _schedule_activity(iat_client, iat_headers, res["reservation_id"])
    r = await iat_client.post(f"/api/activities/{act['activity_id']}/complete", json={
        "performed_datetime": "2026-06-11T10:30:00",
        "notes": "Dog enjoyed the walk.",
    }, headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["billable"] is True
    assert data["performed_by"] == "iat_staff"
    assert data["notes"] == "Dog enjoyed the walk."


@pytest.mark.asyncio
async def test_complete_activity_not_found(iat_client, iat_headers):
    r = await iat_client.post("/api/activities/no-such-id/complete", json={
        "performed_datetime": "2026-06-11T10:00:00",
    }, headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_unperformed_activity(iat_client, iat_headers):
    res = await _make_reservation(iat_client, iat_headers)
    act = await _schedule_activity(iat_client, iat_headers, res["reservation_id"])
    r = await iat_client.delete(f"/api/activities/{act['activity_id']}", headers=iat_headers)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_activity_not_found(iat_client, iat_headers):
    r = await iat_client.delete("/api/activities/no-such-id", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_performed_activity_blocked(iat_client, iat_headers):
    res = await _make_reservation(iat_client, iat_headers)
    act = await _schedule_activity(iat_client, iat_headers, res["reservation_id"])
    await iat_client.post(f"/api/activities/{act['activity_id']}/complete", json={
        "performed_datetime": "2026-06-11T10:00:00",
    }, headers=iat_headers)
    r = await iat_client.delete(f"/api/activities/{act['activity_id']}", headers=iat_headers)
    assert r.status_code == 409
