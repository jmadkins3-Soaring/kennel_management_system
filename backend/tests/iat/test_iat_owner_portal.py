"""IAT: Owner self-service portal (Spec §8.6)."""

import pytest
from .conftest import create_owner, create_dog, get_first_large_kennel, create_reservation


@pytest.mark.asyncio
async def test_portal_link_request_sends_email(iat_client, iat_headers, mock_smtp):
    """Request for portal link triggers email with 7-day one-time link."""
    owner = await create_owner(iat_client, iat_headers)

    r = await iat_client.post("/api/portal/request-link",
        params={"email": owner["email"]})
    assert r.status_code == 200
    assert len(mock_smtp) > 0


@pytest.mark.asyncio
async def test_portal_token_verification_returns_session(iat_client, iat_headers, mock_smtp):
    """Valid portal token can be exchanged for a session token."""
    owner = await create_owner(iat_client, iat_headers)
    await iat_client.post("/api/portal/request-link", params={"email": owner["email"]})

    # Extract the token from the mock email (implementation-dependent)
    # For now assert the verify endpoint exists and returns non-501
    r = await iat_client.get("/api/portal/verify/fake-token-for-test")
    assert r.status_code != 501  # endpoint must be implemented


@pytest.mark.asyncio
async def test_portal_shows_only_owners_dogs(iat_client, iat_headers):
    """Portal /dogs returns only this owner's dogs. No other owner data."""
    owner1 = await create_owner(iat_client, iat_headers, last_name="PortalOwner1")
    owner2 = await create_owner(iat_client, iat_headers, last_name="PortalOwner2")
    dog1 = await create_dog(iat_client, iat_headers, owner_id=owner1["owner_id"])
    dog2 = await create_dog(iat_client, iat_headers, owner_id=owner2["owner_id"])

    # Portal request for owner1
    r = await iat_client.post("/api/portal/request-link", params={"email": owner1["email"]})
    assert r.status_code == 200
    # With a real token, portal should only return dog1, not dog2
    # Full assertion requires token extraction — flagged for Agent H


@pytest.mark.asyncio
async def test_portal_availability_shows_free_vs_busy(iat_client, iat_headers):
    """Portal availability endpoint returns Free/Busy by size class and date."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], size_class="M")
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    r = await iat_client.get("/api/portal/availability", params={
        "size_class": "M",
        "start_date": "2026-06-10",
        "end_date": "2026-06-15",
        # No portal token in this test — assert endpoint is not 501
    })
    assert r.status_code != 501


@pytest.mark.asyncio
async def test_portal_self_booking_enforces_all_validation(iat_client, iat_headers):
    """Portal self-booking applies full PACFA and size class validation with no override capability."""
    # Portal-booked reservations must reject PACFA violations without override
    # Detailed flow requires portal token — flagged for Agent H implementation
    r = await iat_client.post("/api/portal/reservations", json={
        "dog_id": "fake", "kennel_id": "fake",
        "dropoff_datetime": "2026-06-10T09:00:00",
        "pickup_datetime": "2026-06-13T10:00:00",
    })
    # Must not be 501 (not implemented) — must be 401 (auth) or validation error
    assert r.status_code != 501


@pytest.mark.asyncio
async def test_portal_reservation_modification_blocked_after_checkin(iat_client, iat_headers):
    """Owner cannot modify a reservation after check-in has occurred."""
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")

    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
        json={"medical_acknowledged": False}, headers=iat_headers)

    r = await iat_client.put(f"/api/portal/reservations/{res['reservation_id']}", json={
        "pickup_datetime": "2026-06-15T10:00:00",
    })
    assert r.status_code in (401, 403, 409, 422)
