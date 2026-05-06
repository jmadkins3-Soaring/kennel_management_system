"""IAT: Multi-dog PACFA validation (Spec §6.4)."""

import pytest
from .conftest import create_owner, create_dog, get_first_large_kennel


@pytest.mark.asyncio
async def test_two_small_dogs_same_kennel_pass_pacfa(iat_client, iat_headers):
    """Two S dogs (4.00 sqft each, short stay) = 8.00 sqft combined < 30 sqft Large kennel."""
    owner = await create_owner(iat_client, iat_headers)
    dog1 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="S")
    dog2 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="S")
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    r1 = await iat_client.post("/api/reservations", json={
        "dog_id": dog1["dog_id"], "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00", "pickup_datetime": "2026-06-12T10:00:00",
    }, headers=iat_headers)
    assert r1.status_code == 201

    r2 = await iat_client.post("/api/reservations", json={
        "dog_id": dog2["dog_id"], "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00", "pickup_datetime": "2026-06-12T10:00:00",
    }, headers=iat_headers)
    assert r2.status_code == 201


@pytest.mark.asyncio
async def test_two_xl_dogs_combined_sqft_exceeds_large_kennel(iat_client, iat_headers):
    """Two XL dogs (12.25 sqft each) = 24.50 sqft combined < 30 sqft — actually passes.
    Three XL dogs = 36.75 > 30 sqft — must be hard-blocked."""
    owner = await create_owner(iat_client, iat_headers)
    dog1 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="XL")
    dog2 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="XL")
    dog3 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="XL")
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    await iat_client.post("/api/reservations", json={
        "dog_id": dog1["dog_id"], "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00", "pickup_datetime": "2026-06-12T10:00:00",
    }, headers=iat_headers)
    await iat_client.post("/api/reservations", json={
        "dog_id": dog2["dog_id"], "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00", "pickup_datetime": "2026-06-12T10:00:00",
    }, headers=iat_headers)

    # Third XL dog pushes combined to 36.75 > 30 — hard block
    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog3["dog_id"], "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00", "pickup_datetime": "2026-06-12T10:00:00",
    }, headers=iat_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_multi_dog_pacfa_no_override_available(iat_client, iat_headers):
    """PACFA sqft violation for multi-dog must have no override path — hard block."""
    owner = await create_owner(iat_client, iat_headers)
    dog1 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="XL")
    dog2 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="XL")
    dog3 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="XL")
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    await iat_client.post("/api/reservations", json={
        "dog_id": dog1["dog_id"], "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00", "pickup_datetime": "2026-06-12T10:00:00",
    }, headers=iat_headers)
    await iat_client.post("/api/reservations", json={
        "dog_id": dog2["dog_id"], "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00", "pickup_datetime": "2026-06-12T10:00:00",
    }, headers=iat_headers)

    # Even with override=true in body, must be blocked
    r = await iat_client.post("/api/reservations", json={
        "dog_id": dog3["dog_id"], "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00", "pickup_datetime": "2026-06-12T10:00:00",
        "force_override": True,  # should not exist / be honored
    }, headers=iat_headers)
    assert r.status_code == 422
