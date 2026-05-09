"""IAT: Staff authentication route."""

import pytest


@pytest.mark.asyncio
async def test_login_valid_credentials(iat_client):
    r = await iat_client.post("/api/auth/login", data={
        "username": "iat_staff",
        "password": "iat_pass",
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(iat_client):
    r = await iat_client.post("/api/auth/login", data={
        "username": "iat_staff",
        "password": "wrong_password",
    })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(iat_client):
    r = await iat_client.post("/api/auth/login", data={
        "username": "nobody",
        "password": "anything",
    })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_without_token(iat_client):
    r = await iat_client.get("/api/owners")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_bad_token(iat_client):
    r = await iat_client.get("/api/owners", headers={"Authorization": "Bearer bad.token.here"})
    assert r.status_code == 401
