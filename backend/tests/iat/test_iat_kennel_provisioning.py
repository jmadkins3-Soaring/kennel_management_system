"""IAT: Kennel config provisioning on startup (Spec §6.9)."""

import pytest
import json
import os


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "kennels.json")


@pytest.mark.asyncio
async def test_kennels_provisioned_from_config_on_startup(iat_client, iat_headers):
    """Kennels K-01 through K-04 are provisioned from kennels.json by conftest seed."""
    r = await iat_client.get("/api/kennels", headers=iat_headers)
    assert r.status_code == 200
    kennels = r.json()
    numbers = {k["kennel_number"] for k in kennels}
    assert "K-01" in numbers
    assert "K-02" in numbers


@pytest.mark.asyncio
async def test_provisioned_kennel_has_correct_type(iat_client, iat_headers):
    """Provisioned kennels have kennel_type, max_size_class, and sqft from config."""
    r = await iat_client.get("/api/kennels", headers=iat_headers)
    large = next(k for k in r.json() if k["kennel_number"] == "K-01")
    assert large["kennel_type"] == "Large"
    assert large["max_size_class"] == "XL"
    assert large["sqft"] == pytest.approx(30.0)


@pytest.mark.asyncio
async def test_kennel_deactivation_blocked_with_future_reservation(iat_client, iat_headers):
    """Cannot deactivate kennel with future reservations — must receive 409."""
    from .conftest import create_owner, create_dog, create_reservation, get_first_large_kennel
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    r = await iat_client.put(f"/api/kennels/{kennel['kennel_id']}",
        json={"active": False}, headers=iat_headers)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_kennel_deactivation_allowed_without_future_reservations(iat_client, iat_headers):
    """Kennel with no future reservations can be deactivated."""
    r = await iat_client.get("/api/kennels", headers=iat_headers)
    # Find a kennel with no reservations (all are empty in fresh test DB)
    kennel_id = r.json()[0]["kennel_id"]

    r = await iat_client.put(f"/api/kennels/{kennel_id}",
        json={"active": False}, headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["active"] is False
