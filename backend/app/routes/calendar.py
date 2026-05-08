"""Calendar grid data routes. Day-by-day loading for fast initial render."""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..auth import get_current_user
from ..database import get_session
from ..models.bill import Bill
from ..models.dog import Dog
from ..models.kennel import Kennel
from ..models.kennel_hold import KennelHold
from ..models.owner import Owner
from ..models.reservation import Reservation
from ..config import get_system
from ..services import billing as billing_svc
from ..services import phase as phase_svc

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _overdue_threshold_hours() -> int:
    return get_system().get("pickup_overdue_threshold_hours", 3)
# Duration (in days) that triggers PACFA 181-day alert
PACFA_LONG_STAY_DAYS = 181

PHASES = ["Night", "Morning", "Afternoon", "Evening"]

# Hour used when computing phase membership per phase name
_PHASE_HOURS = {
    "Night": 2,
    "Morning": 8,
    "Afternoon": 14,
    "Evening": 20,
}


def _phase_for_dt(dt: datetime) -> str:
    return phase_svc.get_phase(dt)


def _dt_for_phase(target_date: date, phase: str) -> datetime:
    """Return an example datetime that falls within the given phase on target_date."""
    hour = _PHASE_HOURS[phase]
    return datetime(target_date.year, target_date.month, target_date.day, hour, tzinfo=timezone.utc)


async def _compute_phase_status(
    kennel_id: str,
    target_date: date,
    phase: str,
    session: AsyncSession,
    all_reservations: List[Reservation],
    all_holds: List[KennelHold],
) -> Dict[str, Any]:
    """
    Compute kennel status for one phase cell.
    Precedence: Hold > PostCheckoutHold > Used > Assigned > Free.
    Co-housed dogs (multiple active reservations) are returned via co_residents list.
    """
    for hold in all_holds:
        if hold.kennel_id == kennel_id and hold.active:
            if hold.start_date <= target_date <= hold.end_date:
                return {"status": "Hold", "reservation_id": None, "owner_last_name": None, "co_residents": []}

    kennel_res = [r for r in all_reservations if r.kennel_id == kennel_id and not r.cancelled]
    phase_order = {p: i for i, p in enumerate(PHASES)}

    # PostCheckoutHold is exclusive — no co-housing possible
    for res in kennel_res:
        if res.checkout_datetime and res.checkout_datetime.date() == target_date:
            checkout_phase = _phase_for_dt(res.checkout_datetime)
            try:
                if phase_svc.get_hold_phase(checkout_phase) == phase:
                    return {"status": "PostCheckoutHold", "reservation_id": res.reservation_id, "owner_last_name": None, "co_residents": []}
            except ValueError:
                pass

    # Collect all reservations active in this phase: (priority, reservation)
    # priority 0 = Used, 1 = Assigned
    active: List[tuple] = []
    for res in kennel_res:
        if res.checkin_datetime is not None:
            checkin_date = res.checkin_datetime.date()
            if checkin_date <= target_date:
                if res.checkout_datetime is None or res.checkout_datetime.date() > target_date:
                    active.append((0, res))
                elif res.checkout_datetime.date() == target_date:
                    co_phase = _phase_for_dt(res.checkout_datetime)
                    if phase_order.get(phase, 0) < phase_order.get(co_phase, 0):
                        active.append((0, res))
        else:
            dropoff_date = res.dropoff_datetime.date()
            if dropoff_date <= target_date:
                active.append((1, res))

    if not active:
        return {"status": "Free", "reservation_id": None, "owner_last_name": None, "co_residents": []}

    active.sort(key=lambda x: (x[0], x[1].reservation_id))
    primary_priority, primary_res = active[0]
    primary_status = "Used" if primary_priority == 0 else "Assigned"
    co_residents = [
        {"reservation_id": r.reservation_id, "owner_last_name": None}
        for _, r in active[1:]
    ]

    return {
        "status": primary_status,
        "reservation_id": primary_res.reservation_id,
        "owner_last_name": None,
        "co_residents": co_residents,
    }


async def _get_owner_last_name(reservation_id: str, session: AsyncSession, res_map: Dict) -> Optional[str]:
    """Helper to resolve owner last name from a reservation_id via dog -> owner chain."""
    res = res_map.get(reservation_id)
    if not res:
        return None
    dog = await session.get(Dog, res.dog_id)
    if not dog:
        return None
    owner = await session.get(Owner, dog.owner_id)
    if not owner:
        return None
    return owner.last_name


async def _trigger_14day_billing(session: AsyncSession) -> None:
    """
    Check all checked-in, not-yet-checked-out reservations.
    For each where check_14day_cycle returns True, create a Bill with billing_cycle=2
    if one does not already exist.
    """
    today = datetime.now(timezone.utc).date()

    # Fetch active stays
    stmt = select(Reservation).where(
        Reservation.checkin_datetime.isnot(None),
        Reservation.checkout_datetime.is_(None),
        Reservation.cancelled == False,
    )
    active_reservations = (await session.exec(stmt)).all()

    for res in active_reservations:
        checkin_date = res.checkin_datetime.date()
        if not billing_svc.check_14day_cycle(res.reservation_id, checkin_date, today):
            continue

        # Determine which billing cycle number this is
        days_elapsed = (today - checkin_date).days
        cycle_number = days_elapsed // 14 + 1  # e.g., day 14 → cycle 2

        # Check if a bill for this cycle already exists
        existing = (await session.exec(
            select(Bill).where(
                Bill.reservation_id == res.reservation_id,
                Bill.billing_cycle == cycle_number,
            )
        )).first()
        if existing:
            continue

        # Determine cycle dates
        cycle_start = checkin_date + timedelta(days=(cycle_number - 1) * 14)
        cycle_end = cycle_start + timedelta(days=13)

        # Get dog for size_class
        dog = await session.get(Dog, res.dog_id)
        size_class = dog.size_class.value if dog else "M"

        # Get performed activities for this reservation in the billing window
        from ..models.activity import Activity
        activity_stmt = select(Activity).where(
            Activity.reservation_id == res.reservation_id,
            Activity.performed_datetime.isnot(None),
        )
        activities = (await session.exec(activity_stmt)).all()
        activity_dicts = [
            {
                "activity_type": a.activity_type,
                "performed_datetime": a.performed_datetime.isoformat() if a.performed_datetime else None,
                "performed_by": a.performed_by,
            }
            for a in activities
            if a.performed_datetime and a.performed_datetime.date() >= cycle_start
            and a.performed_datetime.date() <= cycle_end
        ]

        bill_dict = billing_svc.generate_bill(
            reservation_id=res.reservation_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            size_class=size_class,
            activities=activity_dicts,
        )
        bill_dict["billing_cycle"] = cycle_number
        bill_dict["bill_id"] = str(uuid.uuid4())

        new_bill = Bill(
            bill_id=bill_dict["bill_id"],
            reservation_id=res.reservation_id,
            billing_cycle=cycle_number,
            cycle_start_date=cycle_start,
            cycle_end_date=cycle_end,
            line_items=bill_dict["line_items"],
            subtotal=bill_dict["subtotal"],
            total_discounts=bill_dict["total_discounts"],
            total_due=bill_dict["total_due"],
            paid=False,
        )
        session.add(new_bill)

    await session.commit()


@router.get("", summary="Get calendar grid")
async def get_calendar(
    start: date,
    days: int = 10,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Return calendar grid data for all kennels over requested window.
    Each cell: kennel_id, date, phase, status, owner_last_name, reservation_id.
    Status computed per Spec §6.3 precedence: Hold > PostCheckoutHold > Used > Assigned > Free.
    Also triggers 14-day billing cycle checks and includes overdue pickup banner data.
    """
    # Trigger billing cycle check on every calendar load
    await _trigger_14day_billing(session)

    now = datetime.now(timezone.utc)

    # Date range
    date_range = [start + timedelta(days=i) for i in range(days)]

    # Fetch all active kennels
    kennels = (await session.exec(select(Kennel).where(Kennel.active == True))).all()

    # Fetch all relevant reservations (non-cancelled, overlapping the window)
    window_end = date_range[-1]
    all_reservations = (await session.exec(
        select(Reservation).where(Reservation.cancelled == False)
    )).all()

    # Fetch all active holds
    all_holds = (await session.exec(
        select(KennelHold).where(KennelHold.active == True)
    )).all()

    # Build a quick lookup for reservations
    res_map = {r.reservation_id: r for r in all_reservations}

    # Build kennel grid
    kennel_grid = []
    for kennel in kennels:
        day_cells = []
        for target_date in date_range:
            phases_data = {}
            for phase in PHASES:
                cell = await _compute_phase_status(
                    kennel.kennel_id, target_date, phase, session, all_reservations, all_holds
                )
                if cell["reservation_id"]:
                    cell["owner_last_name"] = await _get_owner_last_name(
                        cell["reservation_id"], session, res_map
                    )
                for cr in cell.get("co_residents", []):
                    cr["owner_last_name"] = await _get_owner_last_name(
                        cr["reservation_id"], session, res_map
                    )
                phases_data[phase] = cell
            day_cells.append({"date": target_date.isoformat(), "phases": phases_data})

        kennel_grid.append({
            "kennel_id": kennel.kennel_id,
            "kennel_number": kennel.kennel_number,
            "days": day_cells,
        })

    # Overdue pickups
    overdue_threshold = now - timedelta(hours=_overdue_threshold_hours())
    overdue_pickups = []
    for res in all_reservations:
        if res.cancelled or res.checkout_datetime is not None:
            continue
        if not res.pickup_datetime:
            continue
        pickup_dt = res.pickup_datetime
        # Make timezone-aware for comparison
        if pickup_dt.tzinfo is None:
            pickup_dt = pickup_dt.replace(tzinfo=timezone.utc)
        if pickup_dt < overdue_threshold:
            dog = await session.get(Dog, res.dog_id)
            owner = await session.get(Owner, dog.owner_id) if dog else None
            kennel = await session.get(Kennel, res.kennel_id)
            hours_overdue = (now - pickup_dt).total_seconds() / 3600
            overdue_pickups.append({
                "reservation_id": res.reservation_id,
                "dog_name": dog.name if dog else "",
                "owner_last_name": owner.last_name if owner else "",
                "kennel_number": kennel.kennel_number if kennel else "",
                "pickup_datetime": pickup_dt.isoformat(),
                "hours_overdue": round(hours_overdue, 2),
                "dismissed": res.pickup_overdue_alerted,
            })

    # PACFA 181-day alert
    alerts = []
    active_checkedin = [
        r for r in all_reservations
        if r.checkin_datetime is not None and r.checkout_datetime is None
    ]
    for res in active_checkedin:
        checkin_date = res.checkin_datetime.date()
        duration = (now.date() - checkin_date).days
        if duration >= PACFA_LONG_STAY_DAYS:
            # Check if there is a qualifying activity confirmed today
            from ..models.activity import Activity
            today = now.date()
            qualifying = (await session.exec(
                select(Activity).where(
                    Activity.reservation_id == res.reservation_id,
                    Activity.qualifies_for_pacfa_exception == True,
                    Activity.performed_datetime.isnot(None),
                )
            )).all()
            confirmed_today = any(
                a.performed_datetime and a.performed_datetime.date() == today
                for a in qualifying
            )
            if not confirmed_today:
                dog = await session.get(Dog, res.dog_id)
                alerts.append({
                    "reservation_id": res.reservation_id,
                    "dog_name": dog.name if dog else "",
                    "duration_days": duration,
                    "alert": "PACFA 181-day qualifying activity not confirmed today",
                })

    return {
        "start_date": start.isoformat(),
        "days": days,
        "kennels": kennel_grid,
        "overdue_pickups": overdue_pickups,
        "alerts": alerts,
    }


@router.get("/day/{for_date}", summary="Get single day calendar data")
async def get_calendar_day(
    for_date: date,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> List[Dict[str, Any]]:
    """
    Return a flat list of phase cells for all kennels on a single day.
    Each item: {kennel_id, kennel_number, phase, status, reservation_id, owner_last_name}.
    4 phases × N kennels items total.
    """
    kennels = (await session.exec(select(Kennel).where(Kennel.active == True))).all()
    all_reservations = (await session.exec(
        select(Reservation).where(Reservation.cancelled == False)
    )).all()
    all_holds = (await session.exec(
        select(KennelHold).where(KennelHold.active == True)
    )).all()
    res_map = {r.reservation_id: r for r in all_reservations}

    flat_cells: List[Dict[str, Any]] = []
    for kennel in kennels:
        for phase in PHASES:
            cell = await _compute_phase_status(
                kennel.kennel_id, for_date, phase, session, all_reservations, all_holds
            )
            if cell["reservation_id"]:
                cell["owner_last_name"] = await _get_owner_last_name(
                    cell["reservation_id"], session, res_map
                )
            for cr in cell.get("co_residents", []):
                cr["owner_last_name"] = await _get_owner_last_name(
                    cr["reservation_id"], session, res_map
                )
            flat_cells.append({
                "kennel_id": kennel.kennel_id,
                "kennel_number": kennel.kennel_number,
                "phase": phase,
                **cell,
            })

    return flat_cells


@router.get("/overdue", summary="Get overdue pickup alerts")
async def get_overdue_pickups(
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> List[Dict[str, Any]]:
    """
    Return active overdue pickup alerts (past threshold, not yet dismissed).
    Includes dog name, owner last name, kennel number, time overdue.
    """
    now = datetime.now(timezone.utc)
    overdue_threshold = now - timedelta(hours=_overdue_threshold_hours())

    stmt = select(Reservation).where(
        Reservation.cancelled == False,
        Reservation.checkout_datetime.is_(None),
        Reservation.pickup_datetime.isnot(None),
    )
    reservations = (await session.exec(stmt)).all()

    result = []
    for res in reservations:
        if not res.pickup_datetime:
            continue
        pickup_dt = res.pickup_datetime
        if pickup_dt.tzinfo is None:
            pickup_dt = pickup_dt.replace(tzinfo=timezone.utc)
        if pickup_dt >= overdue_threshold:
            continue

        dog = await session.get(Dog, res.dog_id)
        owner = await session.get(Owner, dog.owner_id) if dog else None
        kennel = await session.get(Kennel, res.kennel_id)
        hours_overdue = (now - pickup_dt).total_seconds() / 3600

        result.append({
            "reservation_id": res.reservation_id,
            "dog_name": dog.name if dog else "",
            "owner_last_name": owner.last_name if owner else "",
            "kennel_number": kennel.kennel_number if kennel else "",
            "pickup_datetime": pickup_dt.isoformat(),
            "hours_overdue": round(hours_overdue, 2),
            "dismissed": res.pickup_overdue_alerted,
        })

    return result


@router.post("/overdue/{reservation_id}/dismiss", summary="Dismiss overdue pickup alert")
async def dismiss_overdue(
    reservation_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Staff dismisses the overdue pickup banner for a specific reservation."""
    res = await session.get(Reservation, reservation_id)
    if not res:
        raise HTTPException(status_code=404, detail="Reservation not found")

    res.pickup_overdue_alerted = True
    res.updated_at = datetime.now(timezone.utc)
    session.add(res)
    await session.commit()
    await session.refresh(res)

    return {"reservation_id": reservation_id, "dismissed": True}
