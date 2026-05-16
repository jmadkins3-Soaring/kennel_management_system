"""IAT: Staff user management endpoints."""

import pytest


# ── GET /api/users/me ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_me_as_staff(iat_client, iat_headers):
    r = await iat_client.get("/api/users/me", headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "iat_staff"
    assert data["role"] == "staff"
    assert data["active"] is True
    assert "user_id" in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_get_me_as_admin(iat_client, iat_admin_headers):
    r = await iat_client.get("/api/users/me", headers=iat_admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "iat_admin"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(iat_client):
    r = await iat_client.get("/api/users/me")
    assert r.status_code == 401


# ── GET /api/users ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_users_as_admin(iat_client, iat_admin_headers):
    r = await iat_client.get("/api/users", headers=iat_admin_headers)
    assert r.status_code == 200
    users = r.json()
    assert isinstance(users, list)
    usernames = {u["username"] for u in users}
    assert "iat_staff" in usernames
    assert "iat_admin" in usernames
    for u in users:
        assert "password_hash" not in u


@pytest.mark.asyncio
async def test_list_users_as_staff_forbidden(iat_client, iat_headers):
    r = await iat_client.get("/api/users", headers=iat_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_users_unauthenticated(iat_client):
    r = await iat_client.get("/api/users")
    assert r.status_code == 401


# ── POST /api/users ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_staff_user_as_admin(iat_client, iat_admin_headers):
    payload = {"username": "newstaff", "password": "securepass1", "role": "staff"}
    r = await iat_client.post("/api/users", json=payload, headers=iat_admin_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["username"] == "newstaff"
    assert data["role"] == "staff"
    assert data["active"] is True
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_create_admin_user_as_admin(iat_client, iat_admin_headers):
    payload = {"username": "newadmin", "password": "securepass1", "role": "admin"}
    r = await iat_client.post("/api/users", json=payload, headers=iat_admin_headers)
    assert r.status_code == 201
    assert r.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_create_user_default_role_is_staff(iat_client, iat_admin_headers):
    payload = {"username": "defaultrole", "password": "securepass1"}
    r = await iat_client.post("/api/users", json=payload, headers=iat_admin_headers)
    assert r.status_code == 201
    assert r.json()["role"] == "staff"


@pytest.mark.asyncio
async def test_create_user_duplicate_username(iat_client, iat_admin_headers):
    payload = {"username": "iat_staff", "password": "securepass1", "role": "staff"}
    r = await iat_client.post("/api/users", json=payload, headers=iat_admin_headers)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_create_user_invalid_role(iat_client, iat_admin_headers):
    payload = {"username": "badrole", "password": "securepass1", "role": "superuser"}
    r = await iat_client.post("/api/users", json=payload, headers=iat_admin_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_user_short_password(iat_client, iat_admin_headers):
    payload = {"username": "shortpw", "password": "short", "role": "staff"}
    r = await iat_client.post("/api/users", json=payload, headers=iat_admin_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_user_as_staff_forbidden(iat_client, iat_headers):
    payload = {"username": "anyuser", "password": "securepass1", "role": "staff"}
    r = await iat_client.post("/api/users", json=payload, headers=iat_headers)
    assert r.status_code == 403


# ── PUT /api/users/{user_id} ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_user_username_as_admin(iat_client, iat_admin_headers):
    users = (await iat_client.get("/api/users", headers=iat_admin_headers)).json()
    staff = next(u for u in users if u["username"] == "iat_staff")

    r = await iat_client.put(
        f"/api/users/{staff['user_id']}",
        json={"username": "renamed_staff"},
        headers=iat_admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["username"] == "renamed_staff"


@pytest.mark.asyncio
async def test_update_user_role_as_admin(iat_client, iat_admin_headers):
    users = (await iat_client.get("/api/users", headers=iat_admin_headers)).json()
    staff = next(u for u in users if u["username"] == "iat_staff")

    r = await iat_client.put(
        f"/api/users/{staff['user_id']}",
        json={"role": "admin"},
        headers=iat_admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_update_user_deactivate_as_admin(iat_client, iat_admin_headers):
    users = (await iat_client.get("/api/users", headers=iat_admin_headers)).json()
    staff = next(u for u in users if u["username"] == "iat_staff")

    r = await iat_client.put(
        f"/api/users/{staff['user_id']}",
        json={"active": False},
        headers=iat_admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["active"] is False


@pytest.mark.asyncio
async def test_update_user_duplicate_username(iat_client, iat_admin_headers):
    users = (await iat_client.get("/api/users", headers=iat_admin_headers)).json()
    staff = next(u for u in users if u["username"] == "iat_staff")

    r = await iat_client.put(
        f"/api/users/{staff['user_id']}",
        json={"username": "iat_admin"},
        headers=iat_admin_headers,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_update_user_not_found(iat_client, iat_admin_headers):
    r = await iat_client.put(
        "/api/users/nonexistent-id",
        json={"role": "staff"},
        headers=iat_admin_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_user_invalid_role(iat_client, iat_admin_headers):
    users = (await iat_client.get("/api/users", headers=iat_admin_headers)).json()
    staff = next(u for u in users if u["username"] == "iat_staff")

    r = await iat_client.put(
        f"/api/users/{staff['user_id']}",
        json={"role": "superadmin"},
        headers=iat_admin_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_user_as_staff_forbidden(iat_client, iat_headers, iat_admin_headers):
    users = (await iat_client.get("/api/users", headers=iat_admin_headers)).json()
    staff = next(u for u in users if u["username"] == "iat_staff")

    r = await iat_client.put(
        f"/api/users/{staff['user_id']}",
        json={"role": "admin"},
        headers=iat_headers,
    )
    assert r.status_code == 403


# ── POST /api/users/{user_id}/reset-password ─────────────────────────────────

@pytest.mark.asyncio
async def test_reset_password_as_admin(iat_client, iat_admin_headers):
    users = (await iat_client.get("/api/users", headers=iat_admin_headers)).json()
    staff = next(u for u in users if u["username"] == "iat_staff")

    r = await iat_client.post(
        f"/api/users/{staff['user_id']}/reset-password",
        json={"new_password": "newpassword123"},
        headers=iat_admin_headers,
    )
    assert r.status_code == 204

    # Verify old credentials no longer work
    r = await iat_client.post("/api/auth/login", data={"username": "iat_staff", "password": "iat_pass"})
    assert r.status_code == 401

    # Verify new credentials work
    r = await iat_client.post("/api/auth/login", data={"username": "iat_staff", "password": "newpassword123"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_short_rejected(iat_client, iat_admin_headers):
    users = (await iat_client.get("/api/users", headers=iat_admin_headers)).json()
    staff = next(u for u in users if u["username"] == "iat_staff")

    r = await iat_client.post(
        f"/api/users/{staff['user_id']}/reset-password",
        json={"new_password": "short"},
        headers=iat_admin_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_reset_password_user_not_found(iat_client, iat_admin_headers):
    r = await iat_client.post(
        "/api/users/nonexistent-id/reset-password",
        json={"new_password": "newpassword123"},
        headers=iat_admin_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_reset_password_as_staff_forbidden(iat_client, iat_headers, iat_admin_headers):
    users = (await iat_client.get("/api/users", headers=iat_admin_headers)).json()
    staff = next(u for u in users if u["username"] == "iat_staff")

    r = await iat_client.post(
        f"/api/users/{staff['user_id']}/reset-password",
        json={"new_password": "newpassword123"},
        headers=iat_headers,
    )
    assert r.status_code == 403
