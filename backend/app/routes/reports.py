"""Reports routes — all return PDF with business branding."""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..auth import get_current_user
from ..database import get_session
from ..models.bill import Bill
from ..models.dog import Dog
from ..models.incident import Incident
from ..models.issue import Issue
from ..models.kennel import Kennel
from ..models.owner import Owner
from ..models.reservation import Reservation
from ..services import pdf as pdf_svc
from ..services import phase as phase_svc

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/pacfa", summary="PACFA Compliance Report (PDF)")
async def report_pacfa(
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """
    Point-in-time PACFA compliance for all active stays.
    Columns: dog, size_class, kennel, kennel_sqft, required_sqft, duration_multiplier,
    combined_sqft (multi-dog), pass/fail, 181+ day activity gap warnings.
    """
    now = datetime.now(timezone.utc)

    # Active stays: checked in, not checked out, not cancelled
    stmt = select(Reservation).where(
        Reservation.checkin_datetime.isnot(None),
        Reservation.checkout_datetime.is_(None),
        Reservation.cancelled == False,
    )
    active_reservations = (await session.exec(stmt)).all()

    active_stays: List[Dict[str, Any]] = []
    for res in active_reservations:
        dog = await session.get(Dog, res.dog_id)
        if not dog:
            continue
        owner = await session.get(Owner, dog.owner_id)
        kennel = await session.get(Kennel, res.kennel_id)

        checkin_date = res.checkin_datetime.date()
        duration_days = (now.date() - checkin_date).days

        # Check for qualifying PACFA activities today
        from ..models.activity import Activity
        today = now.date()
        qualifying_stmt = select(Activity).where(
            Activity.reservation_id == res.reservation_id,
            Activity.qualifies_for_pacfa_exception == True,
            Activity.performed_datetime.isnot(None),
        )
        qualifying_activities = (await session.exec(qualifying_stmt)).all()
        has_qualifying_today = any(
            a.performed_datetime and a.performed_datetime.date() == today
            for a in qualifying_activities
        )

        multiplier = phase_svc.get_pacfa_multiplier(duration_days, has_qualifying_today)
        kennel_sqft = kennel.sqft if kennel else 0.0

        # Minimum sqft requirements per size class (PACFA baseline 10 sqft per dog)
        size_sqft_required: Dict[str, float] = {
            "XS": 10.0, "S": 10.0, "M": 12.0, "L": 15.0, "XL": 20.0,
        }
        base_sqft = size_sqft_required.get(dog.size_class.value, 10.0)
        required_sqft = base_sqft * multiplier
        compliant = kennel_sqft >= required_sqft

        active_stays.append({
            "reservation_id": res.reservation_id,
            "dog_name": dog.name,
            "owner_name": f"{owner.first_name} {owner.last_name}" if owner else "",
            "size_class": dog.size_class.value,
            "kennel_id": kennel.kennel_number if kennel else "",
            "kennel_sqft": kennel_sqft,
            "required_sqft": required_sqft,
            "duration_multiplier": multiplier,
            "duration_days": duration_days,
            "compliant": compliant,
            "checkin_date": checkin_date.isoformat(),
            "vaccinations": "See records",
        })

    pdf_path = await pdf_svc.generate_pacfa_report(active_stays)
    if not pdf_path:
        raise HTTPException(status_code=500, detail="PDF generation failed")

    return FileResponse(pdf_path, media_type="application/pdf", filename="pacfa_report.pdf")


@router.get("/occupancy", summary="Occupancy Rate Report (PDF)")
async def report_occupancy(
    start_date: date,
    end_date: date,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Kennel utilization % by day, size class breakdown, peak occupancy dates."""
    # Total active kennels
    all_kennels = (await session.exec(select(Kennel).where(Kennel.active == True))).all()
    total_kennels = len(all_kennels)

    # All non-cancelled reservations
    all_reservations = (await session.exec(
        select(Reservation).where(Reservation.cancelled == False)
    )).all()

    daily_data: List[Dict[str, Any]] = []
    current = start_date
    while current <= end_date:
        # Count kennels with an active stay on this day
        occupied_kennel_ids: set = set()
        for res in all_reservations:
            if res.checkin_datetime is None:
                continue
            checkin_d = res.checkin_datetime.date()
            checkout_d = res.checkout_datetime.date() if res.checkout_datetime else None
            if checkin_d <= current and (checkout_d is None or checkout_d > current):
                occupied_kennel_ids.add(res.kennel_id)

        occupied = len(occupied_kennel_ids)
        rate = (occupied / total_kennels * 100.0) if total_kennels > 0 else 0.0
        daily_data.append({
            "date": current.isoformat(),
            "occupied": occupied,
            "total_kennels": total_kennels,
            "occupancy_rate": rate,
        })
        current += timedelta(days=1)

    pdf_path = await pdf_svc.generate_occupancy_report(start_date, end_date, daily_data)
    if not pdf_path:
        raise HTTPException(status_code=500, detail="PDF generation failed")

    return FileResponse(pdf_path, media_type="application/pdf", filename="occupancy_report.pdf")


@router.get("/revenue", summary="Revenue Summary Report (PDF)")
async def report_revenue(
    start_date: date,
    end_date: date,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Total revenue, revenue by size class, activity revenue, discount totals, unpaid balance summary."""
    # Query bills whose cycle dates overlap the requested range
    stmt = select(Bill).where(
        Bill.cycle_start_date <= end_date,
        Bill.cycle_end_date >= start_date,
    )
    bills = (await session.exec(stmt)).all()

    total_revenue = 0.0
    kennel_stay_revenue = 0.0
    activity_revenue = 0.0
    total_discounts = 0.0
    unpaid_balance = 0.0

    # Daily breakdown dict
    daily_dict: Dict[str, float] = {}

    for bill in bills:
        subtotal = bill.subtotal or 0.0
        discounts = bill.total_discounts or 0.0
        due = bill.total_due or 0.0

        total_revenue += subtotal
        total_discounts += discounts
        if not bill.paid:
            unpaid_balance += due

        # Line item breakdown
        for item in (bill.line_items or []):
            item_amount = item.get("amount", 0.0)
            item_discount = item.get("discount", 0.0)
            if item.get("type") == "KennelStay":
                kennel_stay_revenue += item_amount
            elif item.get("type") == "Activity":
                activity_revenue += item_amount

        # Assign revenue to cycle_start_date for daily breakdown
        day_key = bill.cycle_start_date.isoformat()
        daily_dict[day_key] = daily_dict.get(day_key, 0.0) + subtotal

    net_revenue = total_revenue - total_discounts

    # Build sorted daily breakdown
    daily_breakdown = [
        {"date": d, "revenue": rev}
        for d, rev in sorted(daily_dict.items())
    ]

    data = {
        "total_revenue": total_revenue,
        "kennel_stay_revenue": kennel_stay_revenue,
        "activity_revenue": activity_revenue,
        "total_discounts": total_discounts,
        "net_revenue": net_revenue,
        "unpaid_balance": unpaid_balance,
        "daily_breakdown": daily_breakdown,
    }

    pdf_path = await pdf_svc.generate_revenue_report(start_date, end_date, data)
    if not pdf_path:
        raise HTTPException(status_code=500, detail="PDF generation failed")

    return FileResponse(pdf_path, media_type="application/pdf", filename="revenue_report.pdf")


@router.get("/upcoming", summary="Upcoming Check-ins and Check-outs Report (PDF)")
async def report_upcoming(
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Today + next 7 days: dog name, owner name, kennel, scheduled datetime, phase, status."""
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(days=7)

    # Reservations with dropoff in [now, now+7days] that are not cancelled
    stmt = select(Reservation).where(
        Reservation.cancelled == False,
        Reservation.dropoff_datetime >= now,
        Reservation.dropoff_datetime <= window_end,
    )
    upcoming_reservations = (await session.exec(stmt)).all()

    upcoming: List[Dict[str, Any]] = []
    for res in upcoming_reservations:
        dog = await session.get(Dog, res.dog_id)
        if not dog:
            continue
        owner = await session.get(Owner, dog.owner_id)
        kennel = await session.get(Kennel, res.kennel_id)

        dropoff_phase = phase_svc.get_phase(res.dropoff_datetime)

        upcoming.append({
            "reservation_id": res.reservation_id,
            "dog_name": dog.name,
            "owner_name": f"{owner.first_name} {owner.last_name}" if owner else "",
            "event_type": "Check-In",
            "date": res.dropoff_datetime.isoformat(),
            "phase": dropoff_phase,
            "kennel_id": kennel.kennel_number if kennel else "",
            "status": "Scheduled",
        })

    pdf_path = await pdf_svc.generate_upcoming_report(upcoming)
    if not pdf_path:
        raise HTTPException(status_code=500, detail="PDF generation failed")

    return FileResponse(pdf_path, media_type="application/pdf", filename="upcoming_report.pdf")


@router.get("/open-incidents", summary="Open Incidents and Issues Report (PDF)")
async def report_open_incidents(
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """All unresolved incidents and issues with type, dog/kennel, reported date, reported by."""
    # Unresolved incidents
    incident_stmt = select(Incident).where(Incident.resolved == False)
    incidents = (await session.exec(incident_stmt)).all()

    incident_dicts: List[Dict[str, Any]] = []
    for inc in incidents:
        dog = await session.get(Dog, inc.dog_id)
        incident_dicts.append({
            "incident_id": inc.incident_id,
            "dog_name": dog.name if dog else "",
            "incident_type": inc.incident_type.value,
            "description": inc.description,
            "occurred_datetime": inc.occurred_datetime.isoformat(),
            "reported_by": inc.reported_by,
            "reported_at": inc.created_at.isoformat(),
            "severity": inc.incident_type.value,
        })

    # Unresolved issues
    issue_stmt = select(Issue).where(Issue.resolved == False)
    issues = (await session.exec(issue_stmt)).all()

    issue_dicts: List[Dict[str, Any]] = []
    for issue in issues:
        kennel = await session.get(Kennel, issue.kennel_id)
        issue_dicts.append({
            "issue_id": issue.issue_id,
            "kennel_id": kennel.kennel_number if kennel else issue.kennel_id,
            "issue_type": issue.issue_type.value,
            "description": issue.description,
            "reported_datetime": issue.reported_datetime.isoformat(),
            "reported_by": issue.reported_by,
            "reported_at": issue.created_at.isoformat(),
            "status": "Open",
        })

    pdf_path = await pdf_svc.generate_open_incidents_report(incident_dicts, issue_dicts)
    if not pdf_path:
        raise HTTPException(status_code=500, detail="PDF generation failed")

    return FileResponse(pdf_path, media_type="application/pdf", filename="open_incidents_report.pdf")
