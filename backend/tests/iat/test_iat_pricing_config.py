"""IAT: Bill amounts match pricing.json (config-driven billing, Spec §6.5).

Verifies that generate_bill() reads rates from pricing.json rather than
using stale hardcoded values. Tests use the actual config/pricing.json values
so a change to the config file will cause these tests to fail (intentional).
"""

import pytest
from freezegun import freeze_time
from app.config import get_pricing
from .conftest import create_owner, create_dog, get_first_large_kennel, create_reservation


@pytest.mark.asyncio
async def test_nightly_rate_matches_pricing_json(iat_client, iat_headers):
    """Bill total_due for a kennel stay equals pricing.json nightly rate × nights."""
    pricing = get_pricing()
    l_rate = pricing["nightly_rates"]["L"]  # e.g. 40.00

    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"],
                           size_class="L")
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    with freeze_time("2026-07-01 09:00:00"):
        # 3-night stay: July 1 dropoff → July 4 pickup
        # generate_bill uses inclusive start + inclusive end → nights = (end - start).days + 1 = 4
        # But the billing cycle is dropoff date to pickup date (cycle_start=July 1, cycle_end=July 4)
        res = await create_reservation(
            iat_client, iat_headers,
            dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
            dropoff="2026-07-01T09:00:00",
            pickup="2026-07-04T10:00:00",
        )
        r = await iat_client.post(
            f"/api/reservations/{res['reservation_id']}/checkin",
            json={"medical_acknowledged": False},
            headers=iat_headers,
        )
        assert r.status_code == 200

    # Fetch the bill created at check-in
    r = await iat_client.get(
        f"/api/bills?reservation_id={res['reservation_id']}", headers=iat_headers
    )
    assert r.status_code == 200
    bills = r.json()
    assert len(bills) >= 1

    bill = bills[0]
    stay_item = next(li for li in bill["line_items"] if li["type"] == "KennelStay")
    assert stay_item["unit_price"] == l_rate


@pytest.mark.asyncio
async def test_activity_price_matches_pricing_json(iat_client, iat_headers):
    """Activity line item unit_price on a 14-day cycle bill equals pricing.json value.

    Check-in bills capture only the kennel stay.  Activities appear on the
    next billing cycle bill (generated at day 14 via GET /api/calendar).
    """
    pricing = get_pricing()
    walk_price = pricing["activity_prices"]["Nature Walk"]  # e.g. 15.00

    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"],
                           size_class="L")
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    # Long stay (20 days) to trigger a 14-day cycle
    with freeze_time("2026-07-01 09:00:00"):
        res = await create_reservation(
            iat_client, iat_headers,
            dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
            dropoff="2026-07-01T09:00:00",
            pickup="2026-07-21T10:00:00",
        )
        await iat_client.post(
            f"/api/reservations/{res['reservation_id']}/checkin",
            json={"medical_acknowledged": False},
            headers=iat_headers,
        )

    # On day 14 (July 15): complete an activity during the cycle 2 window (July 15–28),
    # then trigger billing via GET /api/calendar.
    with freeze_time("2026-07-15 09:00:00"):
        ra = await iat_client.post(
            "/api/activities",
            json={
                "reservation_id": res["reservation_id"],
                "activity_type": "Nature Walk",
                "scheduled_date": "2026-07-15",
            },
            headers=iat_headers,
        )
        assert ra.status_code == 201
        activity_id = ra.json()["activity_id"]
        await iat_client.post(
            f"/api/activities/{activity_id}/complete",
            json={"performed_datetime": "2026-07-15T09:30:00"},
            headers=iat_headers,
        )

        # Trigger 14-day billing cycle generation
        await iat_client.get(
            "/api/calendar", params={"start": "2026-07-15", "days": 1},
            headers=iat_headers,
        )

    r = await iat_client.get(
        f"/api/bills?reservation_id={res['reservation_id']}", headers=iat_headers
    )
    bills = r.json()
    cycle2 = next((b for b in bills if b["billing_cycle"] == 2), None)
    assert cycle2 is not None, "Cycle 2 bill was not generated"

    activity_items = [li for li in cycle2["line_items"] if li["type"] == "Activity"]
    assert len(activity_items) >= 1, "No activity line items on cycle 2 bill"
    assert activity_items[0]["unit_price"] == walk_price
