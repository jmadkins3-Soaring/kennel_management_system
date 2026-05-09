"""IAT: ActivityType CRUD endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_activity_types_active_only(iat_client, iat_headers):
    """Default list returns only active types (seeded in conftest)."""
    r = await iat_client.get("/api/activity-types", headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert all(at["active"] for at in data)


@pytest.mark.asyncio
async def test_list_activity_types_include_inactive(iat_client, iat_headers):
    """active_only=false returns all types including deactivated ones."""
    # Create and then deactivate one
    r = await iat_client.post("/api/activity-types",
        json={"name": "Deprecated Activity", "qualifies_for_pacfa_exception": False},
        headers=iat_headers)
    assert r.status_code == 201
    at_id = r.json()["activity_type_id"]
    await iat_client.put(f"/api/activity-types/{at_id}",
                         json={"active": False}, headers=iat_headers)

    r = await iat_client.get("/api/activity-types?active_only=false", headers=iat_headers)
    assert r.status_code == 200
    all_types = r.json()
    assert any(not at["active"] for at in all_types)


@pytest.mark.asyncio
async def test_create_activity_type(iat_client, iat_headers):
    r = await iat_client.post("/api/activity-types",
        json={"name": "Agility Training", "qualifies_for_pacfa_exception": True},
        headers=iat_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Agility Training"
    assert data["qualifies_for_pacfa_exception"] is True
    assert data["active"] is True
    assert "activity_type_id" in data


@pytest.mark.asyncio
async def test_update_activity_type_deactivate(iat_client, iat_headers):
    r = await iat_client.post("/api/activity-types",
        json={"name": "Old Trick Class", "qualifies_for_pacfa_exception": False},
        headers=iat_headers)
    at_id = r.json()["activity_type_id"]

    r2 = await iat_client.put(f"/api/activity-types/{at_id}",
                              json={"active": False}, headers=iat_headers)
    assert r2.status_code == 200
    assert r2.json()["active"] is False


@pytest.mark.asyncio
async def test_update_activity_type_pacfa_flag(iat_client, iat_headers):
    r = await iat_client.post("/api/activity-types",
        json={"name": "Swim Session", "qualifies_for_pacfa_exception": False},
        headers=iat_headers)
    at_id = r.json()["activity_type_id"]

    r2 = await iat_client.put(f"/api/activity-types/{at_id}",
                              json={"qualifies_for_pacfa_exception": True}, headers=iat_headers)
    assert r2.status_code == 200
    assert r2.json()["qualifies_for_pacfa_exception"] is True


@pytest.mark.asyncio
async def test_update_activity_type_not_found(iat_client, iat_headers):
    r = await iat_client.put("/api/activity-types/no-such-id",
                             json={"active": False}, headers=iat_headers)
    assert r.status_code == 404
