"""IAT: Global search endpoint (Spec §8.2)."""

import pytest
from .conftest import create_owner, create_dog, create_reservation, get_first_large_kennel


@pytest.mark.asyncio
async def test_search_empty_query_returns_empty(iat_client, iat_headers):
    r = await iat_client.get("/api/search?q=", headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["active_stays"] == []
    assert data["other_results"] == []


@pytest.mark.asyncio
async def test_search_short_query_returns_empty(iat_client, iat_headers):
    r = await iat_client.get("/api/search?q=a", headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["active_stays"] == []
    assert r.json()["other_results"] == []


@pytest.mark.asyncio
async def test_search_owner_by_last_name(iat_client, iat_headers):
    await create_owner(iat_client, iat_headers, last_name="Vandenberg", first_name="Carl")
    r = await iat_client.get("/api/search?q=Vandenberg", headers=iat_headers)
    assert r.status_code == 200
    others = r.json()["other_results"]
    assert any(o["type"] == "owner" and "Vandenberg" in o["display"] for o in others)


@pytest.mark.asyncio
async def test_search_dog_by_name(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="Zephyr", breed="Husky")
    r = await iat_client.get("/api/search?q=Zephyr", headers=iat_headers)
    assert r.status_code == 200
    others = r.json()["other_results"]
    assert any(o["type"] == "dog" and "Zephyr" in o["display"] for o in others)


@pytest.mark.asyncio
async def test_search_dog_by_breed(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="Bolt", breed="Dalmatian")
    r = await iat_client.get("/api/search?q=Dalmatian", headers=iat_headers)
    assert r.status_code == 200
    others = r.json()["other_results"]
    assert any(o["type"] == "dog" for o in others)


@pytest.mark.asyncio
async def test_search_active_stay_by_dog_name(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="Nimbus")
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    # Check in to make it an active stay
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
        json={"medical_acknowledged": False}, headers=iat_headers)

    r = await iat_client.get("/api/search?q=Nimbus", headers=iat_headers)
    assert r.status_code == 200
    active = r.json()["active_stays"]
    assert any(s["dog_name"] == "Nimbus" for s in active)


@pytest.mark.asyncio
async def test_search_active_stay_by_owner_name(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers, last_name="Umberton")
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="Buddy")
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
        json={"medical_acknowledged": False}, headers=iat_headers)

    r = await iat_client.get("/api/search?q=Umberton", headers=iat_headers)
    assert r.status_code == 200
    active = r.json()["active_stays"]
    assert any(s["owner_last_name"] == "Umberton" for s in active)


@pytest.mark.asyncio
async def test_search_no_match_returns_empty_results(iat_client, iat_headers):
    r = await iat_client.get("/api/search?q=xyzxyzxyz", headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["active_stays"] == []
    assert r.json()["other_results"] == []


@pytest.mark.asyncio
async def test_search_dogs_of_matched_owner_included(iat_client, iat_headers):
    """Dogs belonging to a matched owner appear in other_results even without dog-name match."""
    owner = await create_owner(iat_client, iat_headers, last_name="Greystone")
    await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"],
                     name="Pebble", breed="Poodle")
    r = await iat_client.get("/api/search?q=Greystone", headers=iat_headers)
    assert r.status_code == 200
    others = r.json()["other_results"]
    types = [o["type"] for o in others]
    assert "owner" in types
    assert "dog" in types
