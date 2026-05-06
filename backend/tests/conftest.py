"""Shared test fixtures for all backend tests."""

import asyncio
import os
import pytest
import uuid
from datetime import datetime, timezone, date
from typing import AsyncGenerator

os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("CONFIG_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "config"))
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import get_session
from app.auth import hash_password, create_access_token


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_test_engine = create_async_engine(TEST_DB_URL, echo=False)
_TestSession = async_sessionmaker(bind=_test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(autouse=True)
async def reset_db():
    """Fresh schema for every test."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    async with _TestSession() as s:
        yield s


@pytest.fixture
async def client(session) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX AsyncClient wired to the FastAPI app with an overridden DB session."""
    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def staff_user(session) -> dict:
    """Insert a test staff user and return credentials."""
    from app.models.staff_user import StaffUser
    user = StaffUser(
        user_id=str(uuid.uuid4()),
        username="teststaff",
        password_hash=hash_password("testpass123"),
    )
    session.add(user)
    await session.commit()
    return {"username": "teststaff", "password": "testpass123"}


@pytest.fixture
def staff_token(staff_user) -> str:
    return create_access_token(staff_user["username"])


@pytest.fixture
def auth_headers(staff_token) -> dict:
    return {"Authorization": f"Bearer {staff_token}"}


# ── Domain object helpers ──────────────────────────────────────────────────────

@pytest.fixture
async def owner_data() -> dict:
    return {
        "first_name": "Jane",
        "last_name": "Smith",
        "phone_number": "303-555-0101",
        "email": "jane.smith@example.com",
    }


@pytest.fixture
async def dog_data(owner_data) -> dict:
    return {
        "name": "Rex",
        "breed": "Golden Retriever",
        "size_class": "L",
        "medical_status": "Healthy",
    }


@pytest.fixture
async def seeded_owner(client, auth_headers, owner_data) -> dict:
    r = await client.post("/api/owners", json=owner_data, headers=auth_headers)
    return r.json()


@pytest.fixture
async def seeded_large_kennel(session) -> dict:
    from app.models.kennel import Kennel
    k = Kennel(
        kennel_id=str(uuid.uuid4()),
        kennel_number="K-01",
        kennel_type="Large",
        max_size_class="XL",
        sqft=30.0,
        features="interior and exterior space",
        active=True,
        provisioned_from_config=True,
    )
    session.add(k)
    await session.commit()
    await session.refresh(k)
    return k.model_dump()


@pytest.fixture
async def seeded_small_kennel(session) -> dict:
    from app.models.kennel import Kennel
    k = Kennel(
        kennel_id=str(uuid.uuid4()),
        kennel_number="K-02",
        kennel_type="Small",
        max_size_class="M",
        sqft=10.0,
        features="interior only",
        active=True,
        provisioned_from_config=True,
    )
    session.add(k)
    await session.commit()
    await session.refresh(k)
    return k.model_dump()
