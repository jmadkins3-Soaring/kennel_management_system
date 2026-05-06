"""IAT: Quick Add Reservation flow (Spec §7.1)."""

import pytest
from .conftest import create_owner, create_dog, get_first_large_kennel, create_reservation


@pytest.mark.asyncio
async def test_quick_add_new_owner_new_dog_new_reservation(iat_client, iat_headers):
    """Full happy path: new owner → new dog → reservation created, calendar updated."""
    owner = await create_owner(iat_client, iat_headers, last_name="QuickAdd")
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="M")
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    reservation = await create_reservation(
        iat_client, iat_headers,
        dog_id=dog["dog_id"],
        kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00",
        pickup="2026-06-13T10:00:00",
    )

    assert reservation["reservation_id"] is not None
    assert reservation["dog_id"] == dog["dog_id"]
    assert reservation["kennel_id"] == kennel["kennel_id"]
    assert reservation["cancelled"] is False


@pytest.mark.asyncio
async def test_quick_add_phase_derived_from_dropoff_time(iat_client, iat_headers):
    """dropoff_phase must be computed from dropoff_datetime time component."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    reservation = await create_reservation(
        iat_client, iat_headers,
        dog_id=dog["dog_id"],
        kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00",   # Morning
        pickup="2026-06-13T14:00:00",    # Afternoon
    )
    assert reservation["dropoff_phase"] == "Morning"
    assert reservation["pickup_phase"] == "Afternoon"


@pytest.mark.asyncio
async def test_quick_add_size_class_hard_block(iat_client, iat_headers):
    """XL dog cannot be placed in Small kennel (max_size_class=M) — hard block."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="XL")
    r = await iat_client.get("/api/kennels", headers=iat_headers)
    small_kennel = next(k for k in r.json() if k["kennel_type"] == "Small")

    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog["dog_id"],
        "kennel_id": small_kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00",
        "pickup_datetime": "2026-06-13T10:00:00",
    }, headers=iat_headers)
    assert r.status_code == 422  # Unprocessable — hard block


@pytest.mark.asyncio
async def test_quick_add_pacfa_hard_block(iat_client, iat_headers):
    """XL dog with 181+ day stay requires 36.75 sqft — exceeds Small kennel (10 sqft)."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="XL")
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    # 181+ day stay at 3.0x → 12.25 * 3 = 36.75 sqft required → exceeds 30 sqft Large kennel
    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-01-01T09:00:00",
        "pickup_datetime": "2026-07-01T10:00:00",  # 181 days
    }, headers=iat_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_quick_add_phase_conflict_requires_override(iat_client, iat_headers):
    """Second reservation overlapping same kennel+phase must require override checkbox."""
    owner = await create_owner(iat_client, iat_headers)
    dog1 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    dog2 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    await create_reservation(iat_client, iat_headers,
        dog_id=dog1["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    # Conflict: same kennel, overlapping dates
    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog2["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-11T09:00:00",
        "pickup_datetime": "2026-06-14T10:00:00",
    }, headers=iat_headers)
    assert r.status_code in (409, 422)  # Conflict — requires override


@pytest.mark.asyncio
async def test_quick_add_open_ended_pickup_requires_override(iat_client, iat_headers):
    """pickup_open_ended=True without override flag must be rejected."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00",
        "pickup_open_ended": True,
    }, headers=iat_headers)
    assert r.status_code in (409, 422)


@pytest.mark.asyncio
async def test_quick_add_with_prescheduled_activities(iat_client, iat_headers):
    """Activities prescheduled at reservation creation appear in activity list."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    reservation = await create_reservation(
        iat_client, iat_headers,
        dog_id=dog["dog_id"],
        kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00",
        pickup="2026-06-13T10:00:00",
        prescheduled_activities=[
            {"activity_type": "Nature Walk", "scheduled_date": "2026-06-11"},
        ],
    )

    r = await iat_client.get(
        f"/api/activities?reservation_id={reservation['reservation_id']}",
        headers=iat_headers,
    )
    assert r.status_code == 200
    activities = r.json()
    assert len(activities) == 1
    assert activities[0]["activity_type"] == "Nature Walk"
