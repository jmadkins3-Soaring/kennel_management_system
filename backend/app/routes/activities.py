"""Activity scheduling and completion routes."""

from datetime import datetime, timezone
from typing import List, Optional
from datetime import date

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from ..database import get_session
from ..auth import get_current_user
from ..models.activity import Activity, ActivityCreate, ActivityUpdate, ActivityRead, CompleteActivityRequest
from ..models.activity_type import ActivityType

router = APIRouter(prefix="/api/activities", tags=["activities"])


def _to_activity_read(activity: Activity) -> ActivityRead:
    """Convert Activity ORM object to ActivityRead, computing the billable flag."""
    read = ActivityRead.model_validate(activity)
    read.billable = activity.performed_datetime is not None and activity.performed_by is not None
    return read


@router.get("", response_model=List[ActivityRead], summary="List activities")
async def list_activities(
    reservation_id: Optional[str] = None,
    scheduled_date: Optional[date] = None,
    billable_only: bool = False,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> List[ActivityRead]:
    """Filter activities by reservation, date, or billable status."""
    query = select(Activity)

    if reservation_id is not None:
        query = query.where(Activity.reservation_id == reservation_id)

    if scheduled_date is not None:
        query = query.where(Activity.scheduled_date == scheduled_date)

    activities = (await session.exec(query)).all()

    results: List[ActivityRead] = []
    for activity in activities:
        read = _to_activity_read(activity)
        if billable_only and not read.billable:
            continue
        results.append(read)

    return results


@router.post("", response_model=ActivityRead, status_code=201, summary="Schedule activity")
async def create_activity(
    body: ActivityCreate,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ActivityRead:
    """Schedule a new activity. Sets qualifies_for_pacfa_exception from activity type table."""
    # Look up qualifies_for_pacfa_exception from activity_types
    at = (await session.exec(
        select(ActivityType).where(ActivityType.name == body.activity_type)
    )).first()
    qualifies = at.qualifies_for_pacfa_exception if at else False

    activity = Activity(**body.model_dump(), qualifies_for_pacfa_exception=qualifies)
    session.add(activity)
    await session.commit()
    await session.refresh(activity)
    return _to_activity_read(activity)


@router.put("/{activity_id}", response_model=ActivityRead, summary="Update scheduled activity")
async def update_activity(
    activity_id: str,
    body: ActivityUpdate,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ActivityRead:
    """Update scheduled_date or notes for an unperformed activity."""
    activity = await session.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    if activity.performed_datetime is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot update an activity that has already been performed",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(activity, field, value)

    session.add(activity)
    await session.commit()
    await session.refresh(activity)
    return _to_activity_read(activity)


@router.post("/{activity_id}/complete", response_model=ActivityRead, summary="Mark activity as performed")
async def complete_activity(
    activity_id: str,
    body: CompleteActivityRequest,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ActivityRead:
    """Record actual performance. Sets performed_datetime, performed_by (from JWT), billable=true."""
    activity = await session.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    activity.performed_datetime = body.performed_datetime
    activity.performed_by = username

    if body.notes is not None:
        activity.notes = body.notes

    session.add(activity)
    await session.commit()
    await session.refresh(activity)
    return _to_activity_read(activity)


@router.delete("/{activity_id}", status_code=204, summary="Delete scheduled activity")
async def delete_activity(
    activity_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an unperformed scheduled activity."""
    activity = await session.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    if activity.performed_datetime is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete an activity that has already been performed",
        )

    await session.delete(activity)
    await session.commit()
