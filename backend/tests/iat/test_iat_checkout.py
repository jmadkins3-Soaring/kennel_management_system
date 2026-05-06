"""IAT: Check-out flow (Spec §7.3)."""

import pytest
import os
from .conftest import create_owner, create_dog, get_first_large_kennel, create_reservation


async def checked_in_reservation(client, headers, **dog_kwargs):
    owner = await create_owner(client, headers)
    dog = await create_dog(client, headers, owner_id=owner["owner_id"], **dog_kwargs)
    kennel = await get_first_large_kennel(client, headers)
    res = await create_reservation(client, headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-12T10:00:00")
    await client.post(f"/api/reservations/{res['reservation_id']}/checkin",
        json={"medical_acknowledged": False}, headers=headers)
    return owner, dog, kennel, res


@pytest.mark.asyncio
async def test_checkout_healthy_path(iat_client, iat_headers):
    """checkout_healthy=True sets checkout_datetime, checkout_staff, triggers hold."""
    owner, dog, kennel, res = await checked_in_reservation(iat_client, iat_headers)

    r = await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkout",
        json={"checkout_healthy": True}, headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["checkout_datetime"] is not None
    assert data["checkout_staff"] == "iat_staff"
    assert data["checkout_healthy"] is True


@pytest.mark.asyncio
async def test_checkout_unhealthy_requires_notes(iat_client, iat_headers):
    """checkout_healthy=False without checkout_notes must be rejected."""
    owner, dog, kennel, res = await checked_in_reservation(iat_client, iat_headers)

    r = await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkout",
        json={"checkout_healthy": False, "checkout_notes": None}, headers=iat_headers)
    assert r.status_code in (409, 422)


@pytest.mark.asyncio
async def test_checkout_unhealthy_with_notes_succeeds(iat_client, iat_headers):
    """checkout_healthy=False with checkout_notes filled is valid."""
    owner, dog, kennel, res = await checked_in_reservation(iat_client, iat_headers)

    r = await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkout",
        json={"checkout_healthy": False, "checkout_notes": "Dog has a small cut on left paw."}, headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["checkout_healthy"] is False


@pytest.mark.asyncio
async def test_checkout_applies_post_checkout_hold(iat_client, iat_headers, frozen_morning):
    """Morning checkout → kennel enters Afternoon Hold automatically."""
    owner, dog, kennel, res = await checked_in_reservation(iat_client, iat_headers)
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkout",
        json={"checkout_healthy": True}, headers=iat_headers)

    # Check kennel status for Afternoon phase same day
    r = await iat_client.get(
        f"/api/calendar/day/2026-06-10",
        headers=iat_headers,
    )
    assert r.status_code == 200
    cells = r.json()
    kennel_afternoon = next(
        (c for c in cells if c["kennel_id"] == kennel["kennel_id"] and c["phase"] == "Afternoon"),
        None,
    )
    assert kennel_afternoon is not None
    assert kennel_afternoon["status"] == "Hold"


@pytest.mark.asyncio
async def test_checkout_generates_pdf_receipt(iat_client, iat_headers):
    """Checkout generates a PDF receipt file and records receipt_pdf_path on the bill."""
    owner, dog, kennel, res = await checked_in_reservation(iat_client, iat_headers)
    r = await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkout",
        json={"checkout_healthy": True}, headers=iat_headers)
    assert r.status_code == 200

    r = await iat_client.get(f"/api/bills?reservation_id={res['reservation_id']}", headers=iat_headers)
    bills = r.json()
    assert len(bills) > 0
    assert bills[0]["receipt_pdf_path"] is not None
    assert os.path.exists(bills[0]["receipt_pdf_path"])


@pytest.mark.asyncio
async def test_checkout_auto_emails_when_enabled(iat_client, iat_headers, mock_smtp):
    """When auto_email_receipt=true in system.json, receipt is emailed automatically."""
    import json, os
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "system.json")
    with open(config_path) as f:
        orig = json.load(f)

    orig["auto_email_receipt"] = True
    with open(config_path, "w") as f:
        json.dump(orig, f)

    try:
        owner, dog, kennel, res = await checked_in_reservation(iat_client, iat_headers)
        await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkout",
            json={"checkout_healthy": True}, headers=iat_headers)
        assert len(mock_smtp) > 0
    finally:
        orig["auto_email_receipt"] = False
        with open(config_path, "w") as f:
            json.dump(orig, f)


@pytest.mark.asyncio
async def test_checkout_mark_bill_paid(iat_client, iat_headers):
    """Staff marks bill paid after checkout. paid_datetime and paid_confirmed_by are set."""
    owner, dog, kennel, res = await checked_in_reservation(iat_client, iat_headers)
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkout",
        json={"checkout_healthy": True}, headers=iat_headers)

    r = await iat_client.get(f"/api/bills?reservation_id={res['reservation_id']}", headers=iat_headers)
    bill_id = r.json()[0]["bill_id"]

    r = await iat_client.post(f"/api/bills/{bill_id}/paid", headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["paid"] is True
    assert data["paid_datetime"] is not None
    assert data["paid_confirmed_by"] == "iat_staff"
