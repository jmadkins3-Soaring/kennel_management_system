"""IAT: Owner portal — full session token flow, booking, modify, cancel, availability."""

import pytest
from unittest.mock import patch, AsyncMock

from app.routes.portal import _generate_session_token
from .conftest import create_owner, create_dog, create_reservation, get_first_large_kennel


def _portal_headers(owner_id: str) -> dict:
    """Build X-Portal-Token header using a directly-generated session token."""
    return {"X-Portal-Token": _generate_session_token(owner_id)}


# ── Request-link + verify flow ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_request_link_known_email(iat_client, iat_headers, mock_smtp):
    owner = await create_owner(iat_client, iat_headers)
    r = await iat_client.post("/api/portal/request-link",
                              params={"email": owner["email"]})
    assert r.status_code == 200
    assert len(mock_smtp) > 0


@pytest.mark.asyncio
async def test_request_link_unknown_email(iat_client):
    r = await iat_client.post("/api/portal/request-link",
                              params={"email": "nobody@example.com"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_verify_invalid_token_returns_401(iat_client):
    r = await iat_client.get("/api/portal/verify/not-a-real-jwt")
    assert r.status_code == 401


# ── Portal dogs ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_dogs_no_token(iat_client):
    r = await iat_client.get("/api/portal/dogs")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_portal_dogs_returns_own_dogs_only(iat_client, iat_headers):
    owner1 = await create_owner(iat_client, iat_headers, last_name="Portal1")
    owner2 = await create_owner(iat_client, iat_headers, last_name="Portal2")
    dog1 = await create_dog(iat_client, iat_headers, owner_id=owner1["owner_id"], name="DogA")
    await create_dog(iat_client, iat_headers, owner_id=owner2["owner_id"], name="DogB")

    r = await iat_client.get("/api/portal/dogs",
                             headers=_portal_headers(owner1["owner_id"]))
    assert r.status_code == 200
    names = [d["name"] for d in r.json()]
    assert "DogA" in names
    assert "DogB" not in names


# ── Portal reservations ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_reservations_own_only(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    r = await iat_client.get("/api/portal/reservations",
                             headers=_portal_headers(owner["owner_id"]))
    assert r.status_code == 200
    assert len(r.json()) >= 1


# ── Portal booking ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_book_reservation(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    r = await iat_client.post("/api/portal/reservations", json={
        "dog_id": dog["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-07-01T09:00:00",
        "pickup_datetime": "2026-07-05T10:00:00",
    }, headers=_portal_headers(owner["owner_id"]))
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_portal_book_wrong_owner_dog_blocked(iat_client, iat_headers):
    """Booking with a dog that belongs to a different owner is blocked."""
    owner1 = await create_owner(iat_client, iat_headers, last_name="BookOwner1")
    owner2 = await create_owner(iat_client, iat_headers, last_name="BookOwner2")
    dog2 = await create_dog(iat_client, iat_headers, owner_id=owner2["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    r = await iat_client.post("/api/portal/reservations", json={
        "dog_id": dog2["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-07-01T09:00:00",
        "pickup_datetime": "2026-07-05T10:00:00",
    }, headers=_portal_headers(owner1["owner_id"]))
    assert r.status_code in (403, 404, 422)


@pytest.mark.asyncio
async def test_portal_book_no_token(iat_client):
    r = await iat_client.post("/api/portal/reservations", json={
        "dog_id": "x", "kennel_id": "x",
        "dropoff_datetime": "2026-07-01T09:00:00",
        "pickup_datetime": "2026-07-05T10:00:00",
    })
    assert r.status_code == 401


# ── Portal modify ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_modify_reservation(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-07-01T09:00:00", pickup="2026-07-05T10:00:00")

    r = await iat_client.put(f"/api/portal/reservations/{res['reservation_id']}",
                             json={"pickup_datetime": "2026-07-06T10:00:00"},
                             headers=_portal_headers(owner["owner_id"]))
    assert r.status_code == 200
    assert r.json()["pickup_datetime"].startswith("2026-07-06")


@pytest.mark.asyncio
async def test_portal_modify_blocked_after_checkin(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
                          json={"medical_acknowledged": False}, headers=iat_headers)

    r = await iat_client.put(f"/api/portal/reservations/{res['reservation_id']}",
                             json={"pickup_datetime": "2026-06-15T10:00:00"},
                             headers=_portal_headers(owner["owner_id"]))
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_portal_modify_wrong_owner_blocked(iat_client, iat_headers):
    owner1 = await create_owner(iat_client, iat_headers, last_name="ModOwner1")
    owner2 = await create_owner(iat_client, iat_headers, last_name="ModOwner2")
    dog1 = await create_dog(iat_client, iat_headers, owner_id=owner1["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog1["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-07-01T09:00:00", pickup="2026-07-05T10:00:00")

    r = await iat_client.put(f"/api/portal/reservations/{res['reservation_id']}",
                             json={"notes": "hacked"},
                             headers=_portal_headers(owner2["owner_id"]))
    assert r.status_code in (403, 404)


# ── Portal cancel ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_cancel_request(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-07-01T09:00:00", pickup="2026-07-05T10:00:00")

    r = await iat_client.post(f"/api/portal/reservations/{res['reservation_id']}/cancel-request",
                              headers=_portal_headers(owner["owner_id"]))
    assert r.status_code == 200
    data = r.json()
    assert data["reservation_id"] == res["reservation_id"]
    assert "message" in data


@pytest.mark.asyncio
async def test_portal_cancel_already_cancelled(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-07-01T09:00:00", pickup="2026-07-05T10:00:00")

    # Staff cancel first
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/cancel",
                          headers=iat_headers)

    r = await iat_client.post(f"/api/portal/reservations/{res['reservation_id']}/cancel-request",
                              headers=_portal_headers(owner["owner_id"]))
    assert r.status_code == 409


# ── Portal availability ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_availability_returns_dates(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    r = await iat_client.get("/api/portal/availability", params={
        "size_class": "M",
        "start_date": "2026-06-10",
        "end_date": "2026-06-15",
    }, headers=_portal_headers(owner["owner_id"]))
    assert r.status_code == 200
    data = r.json()
    assert "dates" in data
    assert len(data["dates"]) == 6  # inclusive


@pytest.mark.asyncio
async def test_portal_availability_invalid_size_class(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    r = await iat_client.get("/api/portal/availability", params={
        "size_class": "GIGANTIC",
        "start_date": "2026-06-10",
        "end_date": "2026-06-15",
    }, headers=_portal_headers(owner["owner_id"]))
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_portal_availability_end_before_start(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    r = await iat_client.get("/api/portal/availability", params={
        "size_class": "M",
        "start_date": "2026-06-15",
        "end_date": "2026-06-10",
    }, headers=_portal_headers(owner["owner_id"]))
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_portal_availability_no_token(iat_client):
    r = await iat_client.get("/api/portal/availability", params={
        "size_class": "M",
        "start_date": "2026-06-10",
        "end_date": "2026-06-15",
    })
    assert r.status_code == 401
