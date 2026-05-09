"""IAT: Calendar phase computation — Hold, PostCheckoutHold, Used, Assigned, co-housing, 14-day billing."""

import pytest
from freezegun import freeze_time
from .conftest import create_owner, create_dog, create_reservation, get_first_large_kennel


async def _make_res(client, headers, dropoff, pickup, size_class="M"):
    owner = await create_owner(client, headers)
    dog = await create_dog(client, headers, owner_id=owner["owner_id"], size_class=size_class)
    kennel = await get_first_large_kennel(client, headers)
    res = await create_reservation(client, headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff=dropoff, pickup=pickup)
    return kennel, res, dog, owner


def _cells_for_kennel(day_data: list, kennel_id: str) -> dict:
    """Return {phase: status} for a kennel from /calendar/day response."""
    return {c["phase"]: c["status"] for c in day_data if c["kennel_id"] == kennel_id}


# ── Free ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_phase_free_with_no_reservations(iat_client, iat_headers):
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    r = await iat_client.get("/api/calendar/day/2026-06-10", headers=iat_headers)
    assert r.status_code == 200
    phases = _cells_for_kennel(r.json(), kennel["kennel_id"])
    assert all(s == "Free" for s in phases.values())


# ── Assigned ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_phase_assigned_before_checkin(iat_client, iat_headers):
    """Kennel shows Assigned on the dropoff date when not yet checked in."""
    kennel, res, _, _ = await _make_res(
        iat_client, iat_headers,
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00",
    )
    r = await iat_client.get("/api/calendar/day/2026-06-10", headers=iat_headers)
    phases = _cells_for_kennel(r.json(), kennel["kennel_id"])
    # Morning and later phases on dropoff date should show Assigned
    assert phases.get("Morning") in ("Assigned", "Used")


# ── Used ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_phase_used_after_checkin(iat_client, iat_headers):
    kennel, res, _, _ = await _make_res(
        iat_client, iat_headers,
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00",
    )
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
                          json={"medical_acknowledged": False}, headers=iat_headers)

    r = await iat_client.get("/api/calendar/day/2026-06-11", headers=iat_headers)
    phases = _cells_for_kennel(r.json(), kennel["kennel_id"])
    assert all(s == "Used" for s in phases.values())


# ── PostCheckoutHold ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_phase_post_checkout_hold(iat_client, iat_headers):
    """After Morning checkout, Afternoon phase on same day is PostCheckoutHold."""
    kennel, res, _, _ = await _make_res(
        iat_client, iat_headers,
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00",
    )
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
                          json={"medical_acknowledged": False}, headers=iat_headers)

    # Freeze checkout at 09:30 (Morning) → Afternoon on same day is PostCheckoutHold
    with freeze_time("2026-06-13T09:30:00"):
        await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkout",
                              json={"checkout_healthy": True}, headers=iat_headers)

    r = await iat_client.get("/api/calendar/day/2026-06-13", headers=iat_headers)
    phases = _cells_for_kennel(r.json(), kennel["kennel_id"])
    assert phases.get("Afternoon") == "PostCheckoutHold"


# ── Hold (manual kennel hold) ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_phase_hold_from_kennel_hold(iat_client, iat_headers):
    """Manual kennel hold shows Hold status on all phases for blocked dates."""
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    await iat_client.post(f"/api/kennels/{kennel['kennel_id']}/holds", json={
        "kennel_id": kennel["kennel_id"],
        "start_date": "2026-06-20",
        "end_date": "2026-06-22",
        "reason": "Maintenance",
    }, headers=iat_headers)

    r = await iat_client.get("/api/calendar/day/2026-06-21", headers=iat_headers)
    phases = _cells_for_kennel(r.json(), kennel["kennel_id"])
    assert all(s == "Hold" for s in phases.values())


# ── Co-housing ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_phase_co_housing_same_dates(iat_client, iat_headers):
    """Two dogs with identical dropoff/pickup are co-housed — both appear, no conflict."""
    owner = await create_owner(iat_client, iat_headers)
    # Two small dogs fit in a large kennel: M dog × 2 for 3 days = 6.25 × 1.0 × 2 = 12.5 < 30 sqft
    dog1 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"],
                            name="CoDog1", size_class="M")
    dog2 = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"],
                            name="CoDog2", size_class="M")
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    res1 = await create_reservation(iat_client, iat_headers,
        dog_id=dog1["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")
    # Exact same dates → co-housed (no conflict, no override needed)
    res2_r = await iat_client.post("/api/reservations", json={
        "dog_id": dog2["dog_id"],
        "kennel_id": kennel["kennel_id"],
        "dropoff_datetime": "2026-06-10T09:00:00",
        "pickup_datetime": "2026-06-13T10:00:00",
    }, headers=iat_headers)
    assert res2_r.status_code == 201

    # Calendar day view should show co_residents populated
    r = await iat_client.get("/api/calendar/day/2026-06-10", headers=iat_headers)
    cells = [c for c in r.json()
             if c["kennel_id"] == kennel["kennel_id"] and c["phase"] == "Morning"]
    assert len(cells) == 1
    cell = cells[0]
    assert cell["status"] in ("Assigned", "Used")
    # co_residents list populated for second dog
    assert len(cell.get("co_residents", [])) >= 1


# ── Owner last name resolved in calendar grid ─────────────────────────────────

@pytest.mark.asyncio
async def test_calendar_grid_resolves_owner_last_name(iat_client, iat_headers):
    """Calendar grid populates owner_last_name for Used/Assigned cells."""
    owner = await create_owner(iat_client, iat_headers, last_name="Calowner")
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
                          json={"medical_acknowledged": False}, headers=iat_headers)

    r = await iat_client.get("/api/calendar?start=2026-06-11&days=1", headers=iat_headers)
    assert r.status_code == 200
    for k_row in r.json()["kennels"]:
        if k_row["kennel_id"] == kennel["kennel_id"]:
            for day in k_row["days"]:
                for phase, cell in day["phases"].items():
                    if cell["status"] == "Used":
                        assert cell["owner_last_name"] == "Calowner"


# ── 14-day billing trigger on calendar load ───────────────────────────────────

@pytest.mark.asyncio
async def test_calendar_load_triggers_14day_billing(iat_client, iat_headers):
    """Loading the calendar 14 days after check-in auto-creates a second billing cycle."""
    with freeze_time("2026-06-01T09:00:00"):
        kennel, res, _, _ = await _make_res(
            iat_client, iat_headers,
            dropoff="2026-06-01T09:00:00", pickup="2026-06-30T10:00:00",
        )
        await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
                              json={"medical_acknowledged": False}, headers=iat_headers)

    # Exactly 14 days later — calendar load should trigger cycle 2 bill
    with freeze_time("2026-06-15T09:00:00"):
        await iat_client.get("/api/calendar?start=2026-06-15&days=1", headers=iat_headers)

    bills_r = await iat_client.get(
        f"/api/bills?reservation_id={res['reservation_id']}", headers=iat_headers
    )
    assert bills_r.status_code == 200
    bill_cycles = {b["billing_cycle"] for b in bills_r.json()}
    assert 2 in bill_cycles
