"""ActivityType UI-managed reference data routes. Prices live in pricing.json."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..auth import get_current_user
from ..database import get_session
from ..models.activity_type import ActivityType, ActivityTypeCreate, ActivityTypeUpdate

router = APIRouter(prefix="/api/activity-types", tags=["activity-types"])


@router.get("", response_model=List[ActivityType], summary="List activity types")
async def list_activity_types(
    active_only: bool = True,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return activity types. Staff-managed; prices read from pricing.json."""
    stmt = select(ActivityType)
    if active_only:
        stmt = stmt.where(ActivityType.active == True)
    result = await session.exec(stmt)
    return result.all()


@router.post("", response_model=ActivityType, status_code=201, summary="Create activity type")
async def create_activity_type(
    body: ActivityTypeCreate,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Add a new activity type. Name must be unique."""
    activity_type = ActivityType.model_validate(body)
    session.add(activity_type)
    await session.commit()
    await session.refresh(activity_type)
    return activity_type


@router.put("/{activity_type_id}", response_model=ActivityType, summary="Update activity type")
async def update_activity_type(
    activity_type_id: str,
    body: ActivityTypeUpdate,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Activate, deactivate, or update PACFA exception flag. Prices unchanged here."""
    activity_type = await session.get(ActivityType, activity_type_id)
    if not activity_type:
        raise HTTPException(status_code=404, detail="Activity type not found")
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(activity_type, field, value)
    session.add(activity_type)
    await session.commit()
    await session.refresh(activity_type)
    return activity_type
