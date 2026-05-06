"""IAT: Issue report lifecycle (Spec §7.6)."""

import pytest
from .conftest import get_first_large_kennel


@pytest.mark.asyncio
async def test_create_issue_report(iat_client, iat_headers):
    """Issue report created. Does not auto-change kennel status."""
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    r = await iat_client.post("/api/issues", json={
        "kennel_id": kennel["kennel_id"],
        "issue_type": "Maintenance",
        "description": "Latch on kennel door is broken.",
        "reported_datetime": "2026-06-10T08:00:00",
    }, headers=iat_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["reported_by"] == "iat_staff"
    assert data["resolved"] is False


@pytest.mark.asyncio
async def test_issue_does_not_auto_hold_kennel(iat_client, iat_headers):
    """Creating an issue does NOT automatically place kennel on Hold."""
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    await iat_client.post("/api/issues", json={
        "kennel_id": kennel["kennel_id"],
        "issue_type": "Safety",
        "description": "Sharp edge on door frame.",
        "reported_datetime": "2026-06-10T08:00:00",
    }, headers=iat_headers)

    r = await iat_client.get("/api/calendar/day/2026-06-10", headers=iat_headers)
    cells = [c for c in r.json() if c["kennel_id"] == kennel["kennel_id"]]
    for cell in cells:
        assert cell["status"] == "Free"  # No automatic hold


@pytest.mark.asyncio
async def test_manual_hold_after_issue(iat_client, iat_headers):
    """Staff manually places kennel on Hold after creating issue."""
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    r = await iat_client.post(f"/api/kennels/{kennel['kennel_id']}/holds", json={
        "kennel_id": kennel["kennel_id"],
        "start_date": "2026-06-10",
        "end_date": "2026-06-12",
        "reason": "Broken latch — awaiting repair",
    }, headers=iat_headers)
    assert r.status_code == 201

    r = await iat_client.get("/api/calendar/day/2026-06-11", headers=iat_headers)
    kennel_cells = [c for c in r.json() if c["kennel_id"] == kennel["kennel_id"]]
    for cell in kennel_cells:
        assert cell["status"] == "Hold"


@pytest.mark.asyncio
async def test_resolve_issue_and_lift_hold(iat_client, iat_headers):
    """After resolving issue and lifting hold, kennel returns to Free."""
    kennel = await get_first_large_kennel(iat_client, iat_headers)

    ir = await iat_client.post("/api/issues", json={
        "kennel_id": kennel["kennel_id"],
        "issue_type": "Equipment",
        "description": "Water bowl clip broken.",
        "reported_datetime": "2026-06-10T08:00:00",
    }, headers=iat_headers)
    issue_id = ir.json()["issue_id"]

    hold_r = await iat_client.post(f"/api/kennels/{kennel['kennel_id']}/holds", json={
        "kennel_id": kennel["kennel_id"],
        "start_date": "2026-06-10",
        "end_date": "2026-06-10",
        "reason": "Water bowl broken",
    }, headers=iat_headers)
    hold_id = hold_r.json()["hold_id"]

    await iat_client.post(f"/api/issues/{issue_id}/resolve",
        json={"resolution_notes": "Replaced clip."}, headers=iat_headers)
    await iat_client.delete(f"/api/kennels/{kennel['kennel_id']}/holds/{hold_id}", headers=iat_headers)

    r = await iat_client.get(f"/api/kennels/{kennel['kennel_id']}", headers=iat_headers)
    assert r.json().get("current_status") != "Hold"
