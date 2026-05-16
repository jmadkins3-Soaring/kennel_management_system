"""Unit tests: admin bootstrap on first startup."""

import uuid
import pytest


@pytest.mark.asyncio
async def test_bootstrap_creates_admin_when_table_empty(session):
    """_bootstrap_admin creates an admin when ADMIN_USERNAME/PASSWORD are set and table is empty."""
    from app.main import _bootstrap_admin
    from app.models.staff_user import StaffUser
    from app.auth import verify_password
    import app.database as db_module
    from sqlmodel import select

    class _FakeCtx:
        async def __aenter__(self_):
            return session
        async def __aexit__(self_, *_a):
            pass

    with pytest.MonkeyPatch().context() as mp:
        mp.setenv("ADMIN_USERNAME", "firstadmin")
        mp.setenv("ADMIN_PASSWORD", "strongpass99")
        mp.setattr(db_module, "AsyncSessionLocal", lambda: _FakeCtx())
        await _bootstrap_admin()

    result = await session.exec(select(StaffUser).where(StaffUser.username == "firstadmin"))
    user = result.first()
    assert user is not None
    assert user.role == "admin"
    assert user.active is True
    assert verify_password("strongpass99", user.password_hash)


@pytest.mark.asyncio
async def test_bootstrap_skipped_when_table_has_users(session):
    """_bootstrap_admin does nothing if staff_users already has rows."""
    from app.main import _bootstrap_admin
    from app.models.staff_user import StaffUser
    from app.auth import hash_password
    import app.database as db_module
    from sqlmodel import select

    session.add(StaffUser(
        user_id=str(uuid.uuid4()),
        username="existing",
        password_hash=hash_password("existingpass"),
        role="staff",
    ))
    await session.commit()

    class _FakeCtx:
        async def __aenter__(self_):
            return session
        async def __aexit__(self_, *_a):
            pass

    with pytest.MonkeyPatch().context() as mp:
        mp.setenv("ADMIN_USERNAME", "shouldnotexist")
        mp.setenv("ADMIN_PASSWORD", "shouldnotexist99")
        mp.setattr(db_module, "AsyncSessionLocal", lambda: _FakeCtx())
        await _bootstrap_admin()

    result = await session.exec(select(StaffUser).where(StaffUser.username == "shouldnotexist"))
    assert result.first() is None


@pytest.mark.asyncio
async def test_bootstrap_skipped_when_env_vars_missing(session):
    """_bootstrap_admin is a no-op when ADMIN_USERNAME or ADMIN_PASSWORD are absent."""
    from app.main import _bootstrap_admin
    from app.models.staff_user import StaffUser
    from sqlmodel import select

    with pytest.MonkeyPatch().context() as mp:
        mp.delenv("ADMIN_USERNAME", raising=False)
        mp.delenv("ADMIN_PASSWORD", raising=False)
        await _bootstrap_admin()

    result = await session.exec(select(StaffUser))
    assert result.first() is None
