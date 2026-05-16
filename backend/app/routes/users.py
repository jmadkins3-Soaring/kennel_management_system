"""Staff user management routes."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..auth import get_current_staff_user, require_admin, hash_password
from ..database import get_session
from ..models.staff_user import StaffUser

router = APIRouter(prefix="/api/users", tags=["users"])

_VALID_ROLES = {"admin", "staff"}


class UserRead(SQLModel):
    user_id: str
    username: str
    role: str
    active: bool
    created_at: datetime


class UserCreate(SQLModel):
    username: str = Field(max_length=50)
    password: str
    role: str = "staff"


class UserUpdate(SQLModel):
    username: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None


class PasswordReset(SQLModel):
    new_password: str


@router.get("/me", response_model=UserRead, summary="Current user profile")
async def get_me(user: StaffUser = Depends(get_current_staff_user)):
    return user


@router.get("", response_model=List[UserRead], summary="List all users (admin only)")
async def list_users(
    _: StaffUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(select(StaffUser))
    return result.all()


@router.post("", response_model=UserRead, status_code=201, summary="Create user (admin only)")
async def create_user(
    body: UserCreate,
    _: StaffUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    if body.role not in _VALID_ROLES:
        raise HTTPException(status_code=422, detail="role must be 'admin' or 'staff'")
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="password must be at least 8 characters")
    existing = await session.exec(select(StaffUser).where(StaffUser.username == body.username))
    if existing.first():
        raise HTTPException(status_code=409, detail="Username already exists")
    user = StaffUser(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserRead, summary="Update user (admin only)")
async def update_user(
    user_id: str,
    body: UserUpdate,
    _: StaffUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(StaffUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.role is not None and body.role not in _VALID_ROLES:
        raise HTTPException(status_code=422, detail="role must be 'admin' or 'staff'")
    if body.username is not None:
        clash = await session.exec(
            select(StaffUser).where(StaffUser.username == body.username, StaffUser.user_id != user_id)
        )
        if clash.first():
            raise HTTPException(status_code=409, detail="Username already exists")
        user.username = body.username
    if body.role is not None:
        user.role = body.role
    if body.active is not None:
        user.active = body.active
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/{user_id}/reset-password", status_code=204, summary="Reset user password (admin only)")
async def reset_password(
    user_id: str,
    body: PasswordReset,
    _: StaffUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(StaffUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=422, detail="password must be at least 8 characters")
    user.password_hash = hash_password(body.new_password)
    session.add(user)
    await session.commit()
