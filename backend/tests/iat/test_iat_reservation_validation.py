"""IAT: Reservation create/update validation — hard blocks, overrides, prescheduled activities."""

import pytest
from .conftest import create_owner, create_dog, create_reservation, get_first_large_kennel


async def _get_small_kennel(client, headers) -> dict:
    r = await client.get("/api/kennels", headers=headers)
    small = [k for k in r.json() if k["kennel_type"] == "Small" and k["active"]]
    return small[0]


# ── Dog / kennel not found ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_reservation_dog_not_found(iat_client, iat_headers):
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    r = await iat_client.post("/api/reservations", json={
        "dog_id": "no-such-dog",
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00",
        "pickup_datetime": "2026-06-13T10:00:00",
    }, headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_reservation_kennel_not_found(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog["dog_id"],
        "kennel_id": "no-such-kennel",
        "dropoff_datetime": "2026-06-10T09:00:00",
        "pickup_datetime": "2026-06-13T10:00:00",
    }, headers=iat_headers)
    assert r.status_code == 404


# ── Size class hard block ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_reservation_size_class_violation(iat_client, iat_headers):
    """XL dog cannot book a Small kennel (max_size_class=M) — hard block."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="XL")
    small_kennel = await _get_small_kennel(iat_client, iat_headers)
    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog["dog_id"],
        "kennel_id": small_kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00",
        "pickup_datetime": "2026-06-13T10:00:00",
    }, headers=iat_headers)
    assert r.status_code == 422
    assert "size class" in r.json()["detail"].lower()


# ── PACFA sqft hard block ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_reservation_pacfa_single_violation(iat_client, iat_headers):
    """M dog (6.25 sqft base) × 2.0 multiplier (31+ days) = 12.5 sqft > 10 sqft small kennel."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="M")
    small_kennel = await _get_small_kennel(iat_client, iat_headers)
    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog["dog_id"],
        "kennel_id": small_kennel["kennel_id"],
        "dropoff_datetime": "2026-06-01T09:00:00",
        "pickup_datetime": "2026-07-05T10:00:00",  # 34 days → 2.0x multiplier
    }, headers=iat_headers)
    assert r.status_code == 422
    assert "PACFA" in r.json()["detail"]


@pytest.mark.asyncio
async def test_create_reservation_pacfa_multi_dog_violation(iat_client, iat_headers):
    """Two XL dogs (12.25 sqft × 1.5 multiplier each = 36.75 combined) exceed 30 sqft large kennel."""
    owner = await create_owner(iat_client, iat_headers)
    dog1 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"],
                            name="XL1", size_class="XL")
    dog2 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"],
                            name="XL2", size_class="XL")
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    # First dog: 7-day stay (5–30 day range → 1.5x) — 12.25 * 1.5 = 18.375 sqft — passes alone
    await create_reservation(iat_client, iat_headers,
        dog_id=dog1["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-17T10:00:00")

    # Second XL dog with same dates: combined 36.75 > 30 sqft — PACFA multi-dog hard block
    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog2["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00",
        "pickup_datetime": "2026-06-17T10:00:00",
    }, headers=iat_headers)
    assert r.status_code == 422
    assert "PACFA" in r.json()["detail"]


# ── Phase conflict (soft block with override) ─────────────────────────────────

@pytest.mark.asyncio
async def test_create_reservation_phase_conflict_blocked(iat_client, iat_headers):
    """Overlapping (but not identical) reservation dates → 409 without override."""
    owner = await create_owner(iat_client, iat_headers)
    dog1 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="Dog1")
    dog2 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="Dog2")
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    await create_reservation(iat_client, iat_headers,
        dog_id=dog1["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    # Different dates, overlapping range
    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog2["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-11T09:00:00",
        "pickup_datetime": "2026-06-14T10:00:00",
    }, headers=iat_headers)
    assert r.status_code == 409
    assert "conflict" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_reservation_phase_conflict_with_override(iat_client, iat_headers):
    """Phase conflict override=true → 201 with PhaseConflict entry in override_log."""
    owner = await create_owner(iat_client, iat_headers)
    dog1 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="Dog1")
    dog2 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="Dog2")
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    await create_reservation(iat_client, iat_headers,
        dog_id=dog1["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog2["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-11T09:00:00",
        "pickup_datetime": "2026-06-14T10:00:00",
        "override_phase_conflict": True,
    }, headers=iat_headers)
    assert r.status_code == 201
    override_log = r.json().get("override_log", [])
    assert any(e["override_type"] == "PhaseConflict" for e in override_log)


# ── Open-ended pickup (soft block with override) ──────────────────────────────

@pytest.mark.asyncio
async def test_create_reservation_open_ended_blocked(iat_client, iat_headers):
    """pickup_open_ended=True without override → 409."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00",
        "pickup_open_ended": True,
    }, headers=iat_headers)
    assert r.status_code == 409
    assert "open-ended" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_reservation_open_ended_with_override(iat_client, iat_headers):
    """pickup_open_ended with override → 201 with OpenEndedPickup in override_log."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00",
        "pickup_open_ended": True,
        "override_open_ended_pickup": True,
    }, headers=iat_headers)
    assert r.status_code == 201
    override_log = r.json().get("override_log", [])
    assert any(e["override_type"] == "OpenEndedPickup" for e in override_log)


# ── Prescheduled activities ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_reservation_with_prescheduled_activities(iat_client, iat_headers):
    """Activities listed in prescheduled_activities are created with the reservation."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00",
        "pickup_datetime": "2026-06-13T10:00:00",
        "prescheduled_activities": [
            {"activity_type": "Nature Walk", "scheduled_date": "2026-06-11"},
            {"activity_type": "Playtime",    "scheduled_date": "2026-06-12"},
        ],
    }, headers=iat_headers)
    assert r.status_code == 201
    res_id = r.json()["reservation_id"]

    acts = (await iat_client.get(
        f"/api/activities?reservation_id={res_id}", headers=iat_headers
    )).json()
    assert len(acts) == 2
    types = {a["activity_type"] for a in acts}
    assert types == {"Nature Walk", "Playtime"}


# ── Update reservation kennel re-validation ───────────────────────────────────

@pytest.mark.asyncio
async def test_update_reservation_size_class_revalidation(iat_client, iat_headers):
    """Changing kennel on update re-validates size class — L dog blocked from Small kennel."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="L")
    large_kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=large_kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    small_kennel = await _get_small_kennel(iat_client, iat_headers)
    r = await iat_client.put(f"/api/reservations/{res['reservation_id']}",
                             json={"kennel_id": small_kennel["kennel_id"]},
                             headers=iat_headers)
    assert r.status_code == 422
    assert "size class" in r.json()["detail"].lower()
