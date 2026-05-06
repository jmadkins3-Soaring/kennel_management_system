"""IAT-specific fixtures: live test server, SMTP capture, time-travel, PDF assertions."""

import asyncio
import io
import uuid
from datetime import datetime, timezone, timedelta, date
from typing import AsyncGenerator, Optional
from unittest.mock import AsyncMock, patch

import pytest
from freezegun import freeze_time
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app
from app.database import get_session
from app.auth import hash_password, create_access_token
from app.models.staff_user import StaffUser
from app.models.kennel import Kennel
from app.models.activity_type import ActivityType

# Pre-warm FastAPI's get_cached_model_fields for every request-body model.
#
# FastAPI creates ModelField objects (each containing a TypeAdapter) lazily on the
# first request to an endpoint. freeze_time replaces datetime.datetime/date with
# fake classes, so if that first request is inside a freeze_time block, the
# TypeAdapter creation fails with AttributeError/__pydantic_core_schema__.
#
# Calling get_cached_model_fields() here, at import time, creates and caches all
# ModelField objects with the real datetime classes. Subsequent calls inside
# freeze_time blocks hit the cache and succeed.
from fastapi.routing import APIRoute as _APIRoute
from fastapi._compat import get_cached_model_fields as _gcmf

for _route in app.routes:
    if isinstance(_route, _APIRoute):
        for _bp in _route.dependant.body_params:
            _ann = _bp.field_info.annotation
            if hasattr(_ann, 'model_fields'):
                _gcmf(_ann)

IAT_DB_URL = "sqlite+aiosqlite:///:memory:"
_iat_engine = create_async_engine(IAT_DB_URL, echo=False)
_IATSession = async_sessionmaker(bind=_iat_engine, class_=AsyncSession, expire_on_commit=False)

SEED_ACTIVITY_TYPES = [
    {"name": "Nature Walk",               "qualifies_for_pacfa_exception": True},
    {"name": "Playtime",                  "qualifies_for_pacfa_exception": False},
    {"name": "Medication Administration", "qualifies_for_pacfa_exception": False},
    {"name": "Emergency Grooming",        "qualifies_for_pacfa_exception": False},
    {"name": "Play Yard",                 "qualifies_for_pacfa_exception": True},
]


async def _seed_iat_db(session: AsyncSession) -> None:
    """Seed staff user, kennels, and activity types for IAT tests."""
    session.add(StaffUser(
        user_id=str(uuid.uuid4()),
        username="iat_staff",
        password_hash=hash_password("iat_pass"),
    ))
    for i, kt in enumerate([
        {"type": "Large", "max_size_class": "XL", "sqft": 30.0},
        {"type": "Large", "max_size_class": "XL", "sqft": 30.0},
        {"type": "Small", "max_size_class": "M",  "sqft": 10.0},
        {"type": "Small", "max_size_class": "M",  "sqft": 10.0},
    ], start=1):
        session.add(Kennel(
            kennel_id=str(uuid.uuid4()),
            kennel_number=f"K-{i:02d}",
            kennel_type=kt["type"],
            max_size_class=kt["max_size_class"],
            sqft=kt["sqft"],
            active=True,
            provisioned_from_config=True,
        ))
    for at in SEED_ACTIVITY_TYPES:
        session.add(ActivityType(
            activity_type_id=str(uuid.uuid4()),
            **at,
        ))
    await session.commit()


@pytest.fixture(autouse=True)
async def iat_reset_db():
    async with _iat_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    async with _IATSession() as session:
        await _seed_iat_db(session)
    yield


@pytest.fixture
async def iat_session() -> AsyncGenerator[AsyncSession, None]:
    async with _IATSession() as s:
        yield s


@pytest.fixture
async def iat_client(iat_session) -> AsyncGenerator[AsyncClient, None]:
    async def override():
        yield iat_session

    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def iat_token() -> str:
    return create_access_token("iat_staff", expires_delta=timedelta(days=365))


@pytest.fixture
def iat_headers(iat_token) -> dict:
    return {"Authorization": f"Bearer {iat_token}"}


@pytest.fixture
def mock_smtp():
    """Capture emails sent during a test without hitting a real SMTP server."""
    sent = []
    async def fake_send(*args, **kwargs):
        sent.append({"args": args, "kwargs": kwargs})
        return True
    with patch("app.services.email.send_receipt", side_effect=fake_send), \
         patch("app.services.email.send_portal_link", side_effect=fake_send), \
         patch("app.services.email.send_billing_alert", side_effect=fake_send):
        yield sent


@pytest.fixture
def frozen_morning():
    """Freeze time at 09:00 (Morning phase) on a fixed date."""
    with freeze_time("2026-06-01 09:00:00"):
        yield datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def frozen_afternoon():
    with freeze_time("2026-06-01 14:00:00"):
        yield datetime(2026, 6, 1, 14, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def frozen_evening():
    with freeze_time("2026-06-01 19:00:00"):
        yield datetime(2026, 6, 1, 19, 0, 0, tzinfo=timezone.utc)


# ── Reusable IAT workflow helpers ──────────────────────────────────────────────

async def create_owner(client: AsyncClient, headers: dict, **overrides) -> dict:
    data = {
        "first_name": "IAT",
        "last_name": "Owner",
        "phone_number": "303-555-9999",
        "email": "iat@example.com",
        **overrides,
    }
    r = await client.post("/api/owners", json=data, headers=headers)
    assert r.status_code == 201, f"create_owner failed: {r.text}"
    return r.json()


async def create_dog(client: AsyncClient, headers: dict, owner_id: str, **overrides) -> dict:
    data = {
        "owner_id": owner_id,
        "name": "IATDog",
        "breed": "Lab",
        "size_class": "M",
        "medical_status": "Healthy",
        **overrides,
    }
    r = await client.post("/api/dogs", json=data, headers=headers)
    assert r.status_code == 201, f"create_dog failed: {r.text}"
    return r.json()


async def get_first_large_kennel(client: AsyncClient, headers: dict) -> dict:
    r = await client.get("/api/kennels", headers=headers)
    assert r.status_code == 200
    large = [k for k in r.json() if k["kennel_type"] == "Large" and k["active"]]
    return large[0]


async def create_reservation(client: AsyncClient, headers: dict, dog_id: str, kennel_id: str,
                              dropoff: str, pickup: str, **overrides) -> dict:
    data = {
        "dog_id": dog_id,
        "kennel_id": kennel_id,
        "dropoff_datetime": dropoff,
        "pickup_datetime": pickup,
        **overrides,
    }
    r = await client.post("/api/reservations", json=data, headers=headers)
    assert r.status_code == 201, f"create_reservation failed: {r.text}"
    return r.json()


def assert_pdf_contains(pdf_path: str, *expected_strings: str) -> None:
    """Assert that a generated PDF contains all expected strings."""
    import subprocess
    result = subprocess.run(
        ["pdftotext", pdf_path, "-"],
        capture_output=True, text=True,
    )
    text = result.stdout
    for s in expected_strings:
        assert s in text, f"PDF missing expected string: '{s}'"
