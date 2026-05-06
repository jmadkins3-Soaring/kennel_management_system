"""Reservation CRUD + check-in / check-out / cancel workflows."""

from datetime import datetime, timedelta, timezone, date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from ..auth import get_current_user
from ..database import get_session
from ..models.reservation import (
    Reservation, ReservationCreate, ReservationUpdate, ReservationRead,
    CheckInRequest, CheckOutRequest,
)
from ..models.dog import Dog, MedicalStatus
from ..models.kennel import Kennel
from ..models.owner import Owner
from ..models.bill import Bill
from ..models.incident import Incident
from ..models.activity import Activity
from ..models.kennel_hold import KennelHold
from ..services.phase import (
    get_phase, get_hold_phase, get_next_available_phase, compute_stay_duration_days,
)
from ..services import pacfa as pacfa_svc
from ..services import billing as billing_svc


router = APIRouter(prefix="/api/reservations", tags=["reservations"])


# ── Extended create schema ─────────────────────────────────────────────────────

class ReservationCreateRequest(ReservationCreate):
    override_phase_conflict: bool = False
    override_open_ended_pickup: bool = False


# ── Helpers ────────────────────────────────────────────────────────────────────

def _enrich_reservation(res: Reservation) -> ReservationRead:
    """Build a ReservationRead with computed phase and stay_duration_days fields."""
    data = res.model_dump()
    data["dropoff_phase"] = get_phase(res.dropoff_datetime)
    if res.pickup_datetime:
        data["pickup_phase"] = get_phase(res.pickup_datetime)
        data["stay_duration_days"] = compute_stay_duration_days(
            res.dropoff_datetime, res.pickup_datetime
        )
    return ReservationRead(**data)


def _make_override_entry(override_type: str, override_by: str, conflict_description: str) -> dict:
    return {
        "override_type": override_type,
        "override_datetime": datetime.now(timezone.utc).isoformat(),
        "override_by": override_by,
        "conflict_description": conflict_description,
    }


def _ranges_overlap(
    new_dropoff: datetime,
    new_pickup: Optional[datetime],
    existing_dropoff: datetime,
    existing_pickup: Optional[datetime],
) -> bool:
    """Return True if two date ranges overlap. Open-ended (None pickup) extends to infinity."""
    # [new_dropoff, new_pickup) overlaps [existing_dropoff, existing_pickup)
    # Overlap iff: new_dropoff < existing_pickup AND existing_dropoff < new_pickup
    # If either pickup is None, treat as infinite end.
    if new_pickup is None and existing_pickup is None:
        # Both open-ended → always overlap
        return True
    if new_pickup is None:
        # new is open-ended — overlaps if existing starts before the new one ends (infinite)
        # i.e., existing_dropoff can be anything; overlap as long as new_dropoff < existing_pickup
        return new_dropoff < existing_pickup  # type: ignore[operator]
    if existing_pickup is None:
        # existing is open-ended
        return existing_dropoff < new_pickup
    return new_dropoff < existing_pickup and existing_dropoff < new_pickup


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[ReservationRead], summary="List or search reservations")
async def list_reservations(
    dog_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    kennel_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    cancelled: bool = False,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Filter reservations by dog, owner, kennel, or date range."""
    stmt = select(Reservation).where(Reservation.cancelled == cancelled)

    if dog_id:
        stmt = stmt.where(Reservation.dog_id == dog_id)
    if kennel_id:
        stmt = stmt.where(Reservation.kennel_id == kennel_id)
    if start_date:
        stmt = stmt.where(Reservation.dropoff_datetime >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        stmt = stmt.where(Reservation.dropoff_datetime <= datetime.combine(end_date, datetime.max.time()))

    if owner_id:
        # Join through dogs table to filter by owner
        stmt = stmt.join(Dog, Reservation.dog_id == Dog.dog_id).where(Dog.owner_id == owner_id)

    result = await session.exec(stmt)
    reservations = result.all()
    return [_enrich_reservation(r) for r in reservations]


@router.post("", response_model=ReservationRead, status_code=201, summary="Create reservation (Quick Add)")
async def create_reservation(
    body: ReservationCreateRequest,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Full Quick Add flow: validates size class, PACFA sqft, phase overlap, kennel availability.
    Hard blocks: PACFA violation, size mismatch, unresolved incidents.
    Override blocks (logged): phase conflict, open-ended pickup.
    """
    # 1. Load dog
    dog = await session.get(Dog, body.dog_id)
    if dog is None:
        raise HTTPException(status_code=404, detail="Dog not found")

    # 2. Load kennel
    kennel = await session.get(Kennel, body.kennel_id)
    if kennel is None:
        raise HTTPException(status_code=404, detail="Kennel not found")

    # 3. Validate size class (hard block)
    if not pacfa_svc.validate_size_class(dog.size_class.value, kennel.max_size_class.value):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Dog size class {dog.size_class} exceeds kennel max size class "
                f"{kennel.max_size_class}"
            ),
        )

    # 4. Compute stay_days
    stay_days = 0
    if body.pickup_datetime:
        stay_days = compute_stay_duration_days(body.dropoff_datetime, body.pickup_datetime)

    # 5. Validate PACFA sqft for the single dog (hard block)
    if stay_days > 0:
        passes, req_sqft, k_sqft = pacfa_svc.validate_pacfa_single(
            dog.size_class.value, stay_days, kennel.sqft
        )
        if not passes:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"PACFA violation: dog requires {req_sqft:.2f} sqft, "
                    f"kennel provides {k_sqft:.2f} sqft"
                ),
            )

    # 5b. Multi-dog PACFA: check combined sqft with existing co-occupants on this kennel
    # Find other active (non-cancelled) reservations on the same kennel whose dates overlap
    stmt_existing = select(Reservation).where(
        Reservation.kennel_id == body.kennel_id,
        Reservation.cancelled == False,  # noqa: E712
    )
    result_existing = await session.exec(stmt_existing)
    existing_on_kennel = result_existing.all()

    # Collect overlapping co-occupants (used for multi-dog PACFA and phase conflict checks)
    overlapping_res = [
        r for r in existing_on_kennel
        if _ranges_overlap(
            body.dropoff_datetime, body.pickup_datetime,
            r.dropoff_datetime, r.pickup_datetime,
        )
    ]

    validated_co_occupants: set = set()

    if overlapping_res:
        # Use minimum 1 day for PACFA check on open-ended stays
        check_days = stay_days if stay_days > 0 else 1
        co_dog_size_classes: List[dict] = []
        for existing in overlapping_res:
            co_dog = await session.get(Dog, existing.dog_id)
            if co_dog:
                co_dog_size_classes.append({"size_class": co_dog.size_class.value})

        if co_dog_size_classes:
            all_dogs = co_dog_size_classes + [{"size_class": dog.size_class.value}]
            passes_multi, combined_req, k_sqft = pacfa_svc.validate_pacfa_multi(
                all_dogs, check_days, kennel.sqft
            )
            if not passes_multi:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"PACFA multi-dog violation: combined required {combined_req:.2f} sqft "
                        f"exceeds kennel {k_sqft:.2f} sqft"
                    ),
                )
            # PACFA passed — these are valid co-occupants, not scheduling conflicts
            validated_co_occupants = {r.reservation_id for r in overlapping_res}

    override_log: List[dict] = []

    # 6. Check kennel availability (phase conflict).
    # Reservations that passed multi-dog PACFA are valid co-occupants — not conflicts.
    # Phase conflict only applies to overlapping sequential stays that didn't pass co-housing validation.
    conflicting_res = [
        r for r in overlapping_res
        if r.reservation_id not in validated_co_occupants
    ]
    if conflicting_res:
        if not body.override_phase_conflict:
            raise HTTPException(
                status_code=409,
                detail="Kennel has a conflicting reservation. Set override_phase_conflict=true to proceed.",
            )
        # Override allowed — log it
        conflict_res = conflicting_res[0]
        override_log.append(
            _make_override_entry(
                override_type="PhaseConflict",
                override_by=username,
                conflict_description=(
                    f"Kennel {kennel.kennel_number} already has reservation "
                    f"{conflict_res.reservation_id} from "
                    f"{conflict_res.dropoff_datetime.isoformat()} to "
                    f"{conflict_res.pickup_datetime.isoformat() if conflict_res.pickup_datetime else 'open-ended'}"
                ),
            )
        )

    # 8. Check open-ended pickup
    if body.pickup_open_ended and not body.override_open_ended_pickup:
        raise HTTPException(
            status_code=409,
            detail="Open-ended pickup requires override. Set override_open_ended_pickup=true to proceed.",
        )
    if body.pickup_open_ended and body.override_open_ended_pickup:
        override_log.append(
            _make_override_entry(
                override_type="OpenEndedPickup",
                override_by=username,
                conflict_description="Reservation created with open-ended pickup date.",
            )
        )

    # 9. Create the Reservation record
    reservation = Reservation(
        dog_id=body.dog_id,
        kennel_id=body.kennel_id,
        dropoff_datetime=body.dropoff_datetime,
        pickup_datetime=body.pickup_datetime,
        pickup_open_ended=body.pickup_open_ended,
        notes=body.notes,
        override_log=override_log if override_log else None,
    )
    session.add(reservation)
    await session.flush()  # get the reservation_id

    # 10. Create prescheduled activities
    if body.prescheduled_activities:
        for act_data in body.prescheduled_activities:
            raw_date = act_data.get("scheduled_date")
            if isinstance(raw_date, str):
                raw_date = date.fromisoformat(raw_date)
            activity = Activity(
                reservation_id=reservation.reservation_id,
                activity_type=act_data.get("activity_type", ""),
                scheduled_date=raw_date,
            )
            session.add(activity)

    await session.commit()
    await session.refresh(reservation)

    # 11. Return 201 with override_log
    return _enrich_reservation(reservation)


@router.get("/{reservation_id}", response_model=ReservationRead, summary="Get reservation by ID")
async def get_reservation(
    reservation_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return reservation with computed phase and stay_duration_days fields."""
    res = await session.get(Reservation, reservation_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return _enrich_reservation(res)


@router.put("/{reservation_id}", response_model=ReservationRead, summary="Update reservation")
async def update_reservation(
    reservation_id: str,
    body: ReservationUpdate,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Modify dates, kennel, or notes. Re-validates all constraints. Blocked after check-in."""
    res = await session.get(Reservation, reservation_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Reservation not found")

    # Blocked after check-in
    if res.checkin_datetime is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot modify a reservation after check-in",
        )

    # Apply updates
    if body.dropoff_datetime is not None:
        res.dropoff_datetime = body.dropoff_datetime
    if body.pickup_datetime is not None:
        res.pickup_datetime = body.pickup_datetime
    if body.pickup_open_ended is not None:
        res.pickup_open_ended = body.pickup_open_ended
    if body.kennel_id is not None:
        kennel = await session.get(Kennel, body.kennel_id)
        if kennel is None:
            raise HTTPException(status_code=404, detail="Kennel not found")
        # Re-validate size class if kennel changed
        dog = await session.get(Dog, res.dog_id)
        if dog and not pacfa_svc.validate_size_class(dog.size_class.value, kennel.max_size_class.value):
            raise HTTPException(
                status_code=422,
                detail=f"Dog size class {dog.size_class} exceeds kennel max size class {kennel.max_size_class}",
            )
        res.kennel_id = body.kennel_id
    if body.notes is not None:
        res.notes = body.notes

    res.updated_at = datetime.now(timezone.utc)
    session.add(res)
    await session.commit()
    await session.refresh(res)
    return _enrich_reservation(res)


@router.post("/{reservation_id}/checkin", response_model=ReservationRead, summary="Record check-in")
async def checkin(
    reservation_id: str,
    body: CheckInRequest,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Check-in flow: blocks on unresolved incidents (hard). Warns on unpaid prior bills (override).
    Requires medical_acknowledged=true when dog.medical_status != Healthy.
    Records checkin_datetime and checkin_staff.
    """
    # 1. Load reservation
    res = await session.get(Reservation, reservation_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Reservation not found")

    # 2. Already checked in?
    if res.checkin_datetime is not None:
        raise HTTPException(status_code=409, detail="Reservation is already checked in")

    # 3. Not cancelled?
    if res.cancelled:
        raise HTTPException(status_code=409, detail="Cannot check in a cancelled reservation")

    # 4. Load dog
    dog = await session.get(Dog, res.dog_id)
    if dog is None:
        raise HTTPException(status_code=404, detail="Dog not found")

    # 5. Hard block: unresolved incidents
    stmt_incidents = select(Incident).where(
        Incident.dog_id == res.dog_id,
        Incident.resolved == False,  # noqa: E712
    )
    result_incidents = await session.exec(stmt_incidents)
    if result_incidents.first() is not None:
        raise HTTPException(status_code=422, detail="Unresolved incidents block check-in")

    # 6. Soft block: medical status not Healthy without acknowledgement
    if dog.medical_status != MedicalStatus.HEALTHY and not body.medical_acknowledged:
        raise HTTPException(
            status_code=422,
            detail="Medical acknowledgement required",
        )

    # 7. Soft block: unpaid bills for this dog's prior reservations
    stmt_dog_res = select(Reservation).where(
        Reservation.dog_id == res.dog_id,
        Reservation.reservation_id != reservation_id,
    )
    result_dog_res = await session.exec(stmt_dog_res)
    dog_reservations = result_dog_res.all()

    has_unpaid_bill = False
    if dog_reservations:
        prior_res_ids = [r.reservation_id for r in dog_reservations]
        stmt_bills = select(Bill).where(
            Bill.reservation_id.in_(prior_res_ids),  # type: ignore[attr-defined]
            Bill.paid == False,  # noqa: E712
        )
        result_bills = await session.exec(stmt_bills)
        unpaid_bills = result_bills.all()
        has_unpaid_bill = len(unpaid_bills) > 0

    override_log: List[dict] = list(res.override_log) if res.override_log else []

    if has_unpaid_bill:
        if not body.override_unpaid_bill:
            raise HTTPException(status_code=422, detail="Unpaid bill requires override")
        override_log.append(
            _make_override_entry(
                override_type="UnpaidBill",
                override_by=username,
                conflict_description="Check-in proceeded with outstanding unpaid bill(s).",
            )
        )

    # 8 & 9. Set checkin fields
    now = datetime.now(timezone.utc)
    res.checkin_datetime = now
    res.checkin_staff = username
    res.medical_acknowledged = body.medical_acknowledged
    res.updated_at = now

    if override_log != (res.override_log or []):
        res.override_log = override_log
        flag_modified(res, "override_log")

    # 10. Generate first Bill record
    cycle_end = res.pickup_datetime.date() if res.pickup_datetime else res.dropoff_datetime.date()
    bill_data = billing_svc.generate_bill(
        reservation_id=res.reservation_id,
        cycle_start=res.dropoff_datetime.date(),
        cycle_end=cycle_end,
        size_class=dog.size_class.value,
        activities=[],
    )
    # Build bill from returned dict — map only known fields
    bill = Bill(
        bill_id=bill_data["bill_id"],
        reservation_id=bill_data["reservation_id"],
        billing_cycle=1,
        cycle_start_date=bill_data["cycle_start_date"],
        cycle_end_date=bill_data["cycle_end_date"],
        line_items=bill_data["line_items"],
        subtotal=bill_data["subtotal"],
        total_discounts=bill_data["total_discounts"],
        total_due=bill_data["total_due"],
        paid=bill_data["paid"],
    )
    session.add(bill)

    session.add(res)
    await session.commit()
    await session.refresh(res)
    return _enrich_reservation(res)


@router.post("/{reservation_id}/checkout", response_model=ReservationRead, summary="Record check-out")
async def checkout(
    reservation_id: str,
    body: CheckOutRequest,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Check-out flow: requires checkout_healthy OR checkout_notes (not both empty).
    Records checkout_datetime and checkout_staff. Triggers automatic post-checkout hold.
    """
    # 1. Load reservation
    res = await session.get(Reservation, reservation_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Reservation not found")

    # 2. Must be checked in but not checked out
    if res.checkin_datetime is None:
        raise HTTPException(status_code=409, detail="Reservation has not been checked in")
    if res.checkout_datetime is not None:
        raise HTTPException(status_code=409, detail="Reservation is already checked out")

    # 3. Unhealthy checkout requires notes
    if not body.checkout_healthy and (not body.checkout_notes or not body.checkout_notes.strip()):
        raise HTTPException(
            status_code=422,
            detail="checkout_notes required when not healthy",
        )

    # 4. Set checkout fields
    now = datetime.now(timezone.utc)
    res.checkout_datetime = now
    res.checkout_staff = username
    res.checkout_healthy = body.checkout_healthy
    res.checkout_notes = body.checkout_notes
    res.updated_at = now

    # 5. Trigger post-checkout hold
    checkout_phase = get_phase(now)
    try:
        get_hold_phase(checkout_phase)  # validates phase is checkable
        hold_start = now.date()
        # Extend hold to the originally scheduled pickup date so the kennel
        # remains blocked until the reservation period ends (even for early checkouts).
        if res.pickup_datetime:
            hold_end = max(now.date(), res.pickup_datetime.date())
        else:
            _, day_offset = get_next_available_phase(checkout_phase)
            hold_end = (now + timedelta(days=day_offset)).date()

        kennel_hold = KennelHold(
            kennel_id=res.kennel_id,
            start_date=hold_start,
            end_date=hold_end,
            reason="post_checkout_hold",
            created_by=username,
            active=True,
        )
        session.add(kennel_hold)
    except ValueError:
        # Night phase — no hold applicable
        pass

    session.add(res)
    await session.commit()
    await session.refresh(res)

    # 6. Generate PDF receipt and record path on the bill
    try:
        from ..services import pdf as pdf_svc
        stmt_bill = select(Bill).where(Bill.reservation_id == reservation_id)
        bill_record = (await session.exec(stmt_bill)).first()
        if bill_record:
            _dog = await session.get(Dog, res.dog_id)
            _owner = await session.get(Owner, _dog.owner_id) if _dog else None
            bill_dict = {
                "bill_id": bill_record.bill_id,
                "line_items": bill_record.line_items or [],
                "subtotal": bill_record.subtotal,
                "total_discounts": bill_record.total_discounts,
                "total_due": bill_record.total_due,
                "paid": bill_record.paid,
                "cycle_start_date": bill_record.cycle_start_date.isoformat(),
                "cycle_end_date": bill_record.cycle_end_date.isoformat(),
            }
            owner_dict = {
                "name": f"{_owner.first_name} {_owner.last_name}" if _owner else "",
                "email": _owner.email if _owner else "",
            }
            dog_dict = {"name": _dog.name if _dog else ""}
            reservation_dict = {"reservation_id": reservation_id}
            pdf_path = await pdf_svc.generate_receipt(bill_dict, owner_dict, dog_dict, reservation_dict)
            if pdf_path:
                bill_record.receipt_pdf_path = pdf_path
                bill_record.updated_at = now
                session.add(bill_record)
                await session.commit()
    except Exception:
        pass  # PDF failure must not block checkout

    # 7. Auto-email receipt if configured
    try:
        import json, os
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "config", "system.json"
        )
        config_path = os.path.normpath(config_path)
        if os.path.exists(config_path):
            with open(config_path) as f:
                system_cfg = json.load(f)
            if system_cfg.get("auto_email_receipt"):
                from ..services import email as email_svc
                await email_svc.send_receipt(reservation_id=reservation_id)
    except Exception:
        # Email failure must not block the checkout response
        pass

    return _enrich_reservation(res)


@router.post("/{reservation_id}/cancel", response_model=ReservationRead, summary="Cancel reservation")
async def cancel_reservation(
    reservation_id: str,
    requested_by: str = "Staff",
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Soft-cancel a reservation. Records cancel_requested_by and cancel_confirmed_by."""
    res = await session.get(Reservation, reservation_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if requested_by == "Owner":
        # Owner-initiated: record the request, do NOT fully cancel (requires staff confirmation)
        res.cancel_requested_by = "Owner"
        res.cancel_confirmed_by = None
        # Do not set cancelled=True — staff must confirm
    else:
        # Staff-initiated: full cancellation
        res.cancelled = True
        res.cancel_requested_by = "Staff"
        res.cancel_confirmed_by = username

    res.updated_at = datetime.now(timezone.utc)
    session.add(res)
    await session.commit()
    await session.refresh(res)
    return _enrich_reservation(res)
