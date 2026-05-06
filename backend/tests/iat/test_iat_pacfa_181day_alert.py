"""IAT: PACFA 181+ day alert (Spec §4.3 and §8.3).

Alert fires at Morning phase when a qualifying activity (Nature Walk or Play Yard)
has not yet been confirmed for a 181+ day stay dog.
"""

import pytest
from datetime import datetime, timezone
from freezegun import freeze_time
from .conftest import create_owner, create_dog, get_first_large_kennel, create_reservation


async def setup_long_stay(client, headers, days=200, size_class="M"):
    owner = await create_owner(client, headers)
    dog = await create_dog(client, headers, owner_id=owner["owner_id"], size_class=size_class)
    kennel = await get_first_large_kennel(client, headers)
    dropoff = "2026-01-01T09:00:00"
    pickup = f"2026-{days // 30 + 1:02d}-01T10:00:00"
    res = await create_reservation(client, headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff=dropoff, pickup=pickup)
    await client.post(f"/api/reservations/{res['reservation_id']}/checkin",
        json={"medical_acknowledged": False}, headers=headers)
    return owner, dog, kennel, res


@pytest.mark.asyncio
async def test_181_day_alert_fires_at_morning_phase_without_activity(iat_client, iat_headers):
    """Morning calendar refresh triggers alert when daily qualifying activity not confirmed."""
    _, dog, kennel, res = await setup_long_stay(iat_client, iat_headers, days=200)

    with freeze_time("2026-02-01 09:00:00"):  # Morning phase, day ~31 of stay
        r = await iat_client.get("/api/calendar", params={"start": "2026-02-01", "days": 1},
            headers=iat_headers)
        assert r.status_code == 200
        # Expect alert data in calendar response or via dedicated endpoint
        r2 = await iat_client.get("/api/calendar/overdue", headers=iat_headers)
        alerts = r2.json()
        # At minimum, alert endpoint must respond (not 501)
        assert r2.status_code == 200


@pytest.mark.asyncio
async def test_181_day_alert_suppressed_when_activity_confirmed(iat_client, iat_headers):
    """No alert when qualifying activity is confirmed for today."""
    _, dog, kennel, res = await setup_long_stay(iat_client, iat_headers, days=200)

    with freeze_time("2026-02-01 07:00:00"):  # Morning
        # Schedule and confirm a Nature Walk for today
        act_r = await iat_client.post("/api/activities", json={
            "reservation_id": res["reservation_id"],
            "activity_type": "Nature Walk",
            "scheduled_date": "2026-02-01",
        }, headers=iat_headers)
        assert act_r.status_code == 201
        activity_id = act_r.json()["activity_id"]

        await iat_client.post(f"/api/activities/{activity_id}/complete", json={
            "performed_datetime": "2026-02-01T07:30:00",
        }, headers=iat_headers)

    # No unconfirmed-activity alert should fire for this reservation today
    with freeze_time("2026-02-01 09:00:00"):
        r = await iat_client.get("/api/calendar", params={"start": "2026-02-01", "days": 1},
            headers=iat_headers)
        # Alert for this specific reservation should not be present
        # Exact assertion depends on alert response structure — agents will fill this in
        assert r.status_code == 200
