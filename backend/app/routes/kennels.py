"""Kennel routes — status computation, holds, issue listing."""

from datetime import datetime, timezone, date as date_type
from typing import List, Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from ..database import get_session
from ..auth import get_current_user
from ..models.dog import Dog
from ..models.kennel import Kennel, KennelRead, KennelUpdate
from ..models.kennel_hold import KennelHold, KennelHoldCreate
from ..models.owner import Owner
from ..models.reservation import Reservation
from ..models.issue import Issue, IssueRead

router = APIRouter(prefix="/api/kennels", tags=["kennels"])


async def _compute_kennel_status(
    kennel_id: str,
    session: AsyncSession,
    for_datetime: datetime = None,
) -> str:
    """Compute kennel status with precedence: Hold > Used > Assigned > Free."""
    now = for_datetime or datetime.now(timezone.utc)
    today = now.date()

    # Check manual holds
    hold = (await session.exec(
        select(KennelHold).where(
            KennelHold.kennel_id == kennel_id,
            KennelHold.active == True,
            KennelHold.start_date <= today,
            KennelHold.end_date >= today,
        )
    )).first()
    if hold:
        return "Hold"

    # Check active stay (Used): checked in, not yet checked out, not cancelled
    used = (await session.exec(
        select(Reservation).where(
            Reservation.kennel_id == kennel_id,
            Reservation.checkin_datetime.isnot(None),
            Reservation.checkout_datetime.is_(None),
            Reservation.cancelled == False,
        )
    )).first()
    if used:
        return "Used"

    # Check future reservation (Assigned): not yet checked in, not cancelled
    assigned = (await session.exec(
        select(Reservation).where(
            Reservation.kennel_id == kennel_id,
            Reservation.dropoff_datetime > now,
            Reservation.cancelled == False,
            Reservation.checkin_datetime.is_(None),
        )
    )).first()
    if assigned:
        return "Assigned"

    return "Free"


@router.get("", response_model=List[KennelRead], summary="List all kennels with current status")
async def list_kennels(
    for_date: Optional[date_type] = None,
    for_phase: Optional[str] = None,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> List[KennelRead]:
    """Return all active kennels. Optionally compute status for a specific date/phase."""
    # Determine the point-in-time for status computation
    for_datetime: Optional[datetime] = None
    if for_date is not None:
        # Map phase to an hour; default to noon if no phase given
        phase_hours = {
            "Morning": 9,
            "Afternoon": 13,
            "Evening": 17,
            "Night": 21,
        }
        hour = phase_hours.get(for_phase, 12) if for_phase else 12
        for_datetime = datetime(for_date.year, for_date.month, for_date.day, hour, tzinfo=timezone.utc)

    kennels = (await session.exec(select(Kennel).where(Kennel.active == True))).all()

    results: List[KennelRead] = []
    for kennel in kennels:
        status = await _compute_kennel_status(kennel.kennel_id, session, for_datetime)
        read = KennelRead.model_validate(kennel)
        read.current_status = status
        if status in ("Used", "Assigned") and for_datetime:
            read.current_dogs = await _get_current_dogs(kennel.kennel_id, session, for_datetime)
        results.append(read)

    return results


async def _get_current_dogs(kennel_id: str, session: AsyncSession, for_datetime: datetime) -> list:
    """Return [{dog_name, size_class, owner_last_name}] for all active reservations in this kennel."""
    today = for_datetime.date()
    active = (await session.exec(
        select(Reservation).where(
            Reservation.kennel_id == kennel_id,
            Reservation.cancelled == False,
        )
    )).all()
    result = []
    for res in active:
        dropoff_date = res.dropoff_datetime.date()
        if dropoff_date > today:
            continue
        if res.checkout_datetime and res.checkout_datetime.date() < today:
            continue
        dog = await session.get(Dog, res.dog_id)
        if not dog:
            continue
        owner = await session.get(Owner, dog.owner_id)
        result.append({
            "dog_name": dog.name,
            "size_class": dog.size_class if isinstance(dog.size_class, str) else dog.size_class.value,
            "owner_last_name": owner.last_name if owner else "",
        })
    return result


@router.get("/{kennel_id}", response_model=KennelRead, summary="Get kennel detail")
async def get_kennel(
    kennel_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> KennelRead:
    """Retrieve kennel detail including current status."""
    kennel = await session.get(Kennel, kennel_id)
    if not kennel:
        raise HTTPException(status_code=404, detail="Kennel not found")

    status = await _compute_kennel_status(kennel_id, session)
    read = KennelRead.model_validate(kennel)
    read.current_status = status
    return read


@router.put("/{kennel_id}", response_model=KennelRead, summary="Update kennel")
async def update_kennel(
    kennel_id: str,
    body: KennelUpdate,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> KennelRead:
    """Update kennel description, active flag, or features. Deactivation blocked if future reservations exist."""
    kennel = await session.get(Kennel, kennel_id)
    if not kennel:
        raise HTTPException(status_code=404, detail="Kennel not found")

    # Guard: cannot deactivate a kennel that has future non-cancelled reservations
    if body.active is False:
        now = datetime.now(timezone.utc)
        future_res = (await session.exec(
            select(Reservation).where(
                Reservation.kennel_id == kennel_id,
                Reservation.dropoff_datetime > now,
                Reservation.cancelled == False,
            )
        )).first()
        if future_res:
            raise HTTPException(
                status_code=409,
                detail="Cannot deactivate kennel with future reservations",
            )

    # Apply updates for provided fields only
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(kennel, field, value)

    session.add(kennel)
    await session.commit()
    await session.refresh(kennel)

    status = await _compute_kennel_status(kennel_id, session)
    read = KennelRead.model_validate(kennel)
    read.current_status = status
    return read


@router.post("/{kennel_id}/holds", status_code=201, summary="Place manual hold on kennel")
async def place_hold(
    kennel_id: str,
    body: KennelHoldCreate,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> KennelHold:
    """Create a manual admin hold for a date range."""
    kennel = await session.get(Kennel, kennel_id)
    if not kennel:
        raise HTTPException(status_code=404, detail="Kennel not found")

    hold = KennelHold(
        kennel_id=kennel_id,
        start_date=body.start_date,
        end_date=body.end_date,
        reason=body.reason,
        created_by=username,
    )
    session.add(hold)
    await session.commit()
    await session.refresh(hold)
    return hold


@router.delete("/{kennel_id}/holds/{hold_id}", status_code=204, summary="Lift manual hold")
async def lift_hold(
    kennel_id: str,
    hold_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Release an active manual hold. Records released_by and released_at."""
    hold = await session.get(KennelHold, hold_id)
    if not hold or hold.kennel_id != kennel_id:
        raise HTTPException(status_code=404, detail="Hold not found")

    hold.active = False
    hold.released_by = username
    hold.released_at = datetime.now(timezone.utc)

    session.add(hold)
    await session.commit()


@router.get("/{kennel_id}/issues", response_model=List[IssueRead], summary="List kennel issues")
async def list_kennel_issues(
    kennel_id: str,
    resolved: bool = False,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> List[IssueRead]:
    """Return open (or all) issue reports for a kennel."""
    kennel = await session.get(Kennel, kennel_id)
    if not kennel:
        raise HTTPException(status_code=404, detail="Kennel not found")

    query = select(Issue).where(Issue.kennel_id == kennel_id)
    if not resolved:
        query = query.where(Issue.resolved == False)

    issues = (await session.exec(query)).all()
    return [IssueRead.model_validate(i) for i in issues]
