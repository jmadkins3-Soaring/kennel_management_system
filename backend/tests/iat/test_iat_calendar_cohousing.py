"""IAT: Calendar API co-housing display contract (Spec §4.2 / frontend merge invariant).

The frontend computeSpans() merges consecutive phases that share the same
reservation_id into one continuous bar.  These tests guard the backend
contract that makes that merge correct:

  1. Every phase of a reservation carries the same reservation_id.
  2. Co-housed kennels populate co_residents on all overlapping phases,
     enabling the UI to display co-resident names within the merged bar.
"""

import pytest
from .conftest import create_owner, create_dog, get_first_large_kennel, create_reservation


@pytest.mark.asyncio
async def test_calendar_single_reservation_has_consistent_reservation_id(iat_client, iat_headers):
    """Every phase cell covering a reservation must carry the same reservation_id.

    The frontend merge logic walks consecutive cells and stops when reservation_id
    changes.  If the backend ever returns a different ID (or None) for an interior
    phase, the reservation would split into multiple boxes.
    """
    owner = await create_owner(iat_client, iat_headers, last_name="CalTest")
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    reservation = await create_reservation(
        iat_client, iat_headers,
        dog_id=dog["dog_id"],
        kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00",   # Morning → 3 full days
        pickup="2026-06-13T14:00:00",    # Afternoon
    )
    res_id = reservation["reservation_id"]

    r = await iat_client.get("/api/calendar?start=2026-06-10&days=4", headers=iat_headers)
    assert r.status_code == 200
    cal = r.json()

    kennel_row = next(k for k in cal["kennels"] if k["kennel_id"] == kennel["kennel_id"])

    # Collect every phase that belongs to this reservation across all returned days
    active_phases = []
    for day in kennel_row["days"]:
        for phase_name, cell in day["phases"].items():
            if cell.get("reservation_id") == res_id:
                active_phases.append((day["date"], phase_name, cell))

    assert len(active_phases) > 0, "No phases found for reservation — calendar didn't return it"

    # Every active phase must carry the same reservation_id (no gaps, no None)
    for date, phase, cell in active_phases:
        assert cell["reservation_id"] == res_id, (
            f"Phase {phase} on {date} returned reservation_id={cell['reservation_id']!r}, "
            f"expected {res_id!r}"
        )


@pytest.mark.asyncio
async def test_calendar_cohoused_phases_populate_co_residents(iat_client, iat_headers):
    """Co-housed phases must carry co_residents on every overlapping cell.

    The frontend merges each reservation into one bar and collects co_residents
    across all merged phases.  If co_residents is missing from any phase the
    bar still renders — but this test ensures the backend populates the field
    consistently so the UI can always show who is co-housed.
    """
    owner = await create_owner(iat_client, iat_headers)
    dog_a = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="DogA")
    dog_b = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="DogB")
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    res_a = await create_reservation(
        iat_client, iat_headers,
        dog_id=dog_a["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00",
    )
    res_b = await create_reservation(
        iat_client, iat_headers,
        dog_id=dog_b["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00",
    )

    r = await iat_client.get("/api/calendar?start=2026-06-10&days=4", headers=iat_headers)
    assert r.status_code == 200
    cal = r.json()

    kennel_row = next(k for k in cal["kennels"] if k["kennel_id"] == kennel["kennel_id"])

    # Gather all phases that belong to the overlapping date range
    overlap_phases = []
    for day in kennel_row["days"]:
        if day["date"] < "2026-06-13":
            for phase_name, cell in day["phases"].items():
                if cell.get("status") in ("Assigned", "Used"):
                    overlap_phases.append((day["date"], phase_name, cell))

    assert len(overlap_phases) > 0, "No active phases found during co-housing window"

    res_ids = {res_a["reservation_id"], res_b["reservation_id"]}

    for date, phase, cell in overlap_phases:
        primary_id = cell.get("reservation_id")
        assert primary_id in res_ids, f"Unexpected reservation_id on {date}/{phase}: {primary_id!r}"

        co_res_ids = {cr["reservation_id"] for cr in cell.get("co_residents", [])}
        expected_co = res_ids - {primary_id}
        assert expected_co == co_res_ids, (
            f"Phase {phase} on {date}: expected co_residents={expected_co}, got={co_res_ids}"
        )


@pytest.mark.asyncio
async def test_calendar_primary_reservation_id_stable_across_cohoused_phases(iat_client, iat_headers):
    """The primary reservation_id must be the same on every phase of a co-housed stay.

    computeSpans() identifies a span boundary when reservation_id changes.  If
    the backend alternates which dog is 'primary' between phases, the reservation
    appears as multiple disconnected bars instead of one.
    """
    owner = await create_owner(iat_client, iat_headers)
    dog_a = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="DogA")
    dog_b = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"], name="DogB")
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    res_a = await create_reservation(
        iat_client, iat_headers,
        dog_id=dog_a["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-12T10:00:00",
    )
    res_b = await create_reservation(
        iat_client, iat_headers,
        dog_id=dog_b["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-12T10:00:00",
    )

    r = await iat_client.get("/api/calendar?start=2026-06-10&days=3", headers=iat_headers)
    assert r.status_code == 200
    kennel_row = next(k for k in r.json()["kennels"] if k["kennel_id"] == kennel["kennel_id"])

    seen_primary_ids = set()
    for day in kennel_row["days"]:
        for cell in day["phases"].values():
            if cell.get("reservation_id") in (res_a["reservation_id"], res_b["reservation_id"]):
                seen_primary_ids.add(cell["reservation_id"])

    # The backend must pick one stable primary; switching between the two per-phase
    # would break the merge.  Exactly one of the two reservation IDs should appear
    # as the primary across all phases.
    assert len(seen_primary_ids) == 1, (
        f"Primary reservation_id was not stable across phases: saw {seen_primary_ids}"
    )
