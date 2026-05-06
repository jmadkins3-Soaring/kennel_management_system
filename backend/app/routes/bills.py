"""Billing routes — mark paid, apply discount, generate/retrieve PDF receipt."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..auth import get_current_user
from ..database import get_session
from ..models.bill import ApplyDiscountRequest, Bill, BillRead, MarkPaidRequest
from ..models.dog import Dog
from ..models.owner import Owner
from ..models.reservation import Reservation
from ..services import billing as billing_svc
from ..services import email as email_svc
from ..services import pdf as pdf_svc

router = APIRouter(prefix="/api/bills", tags=["bills"])


@router.get("", response_model=List[BillRead], summary="List bills")
async def list_bills(
    reservation_id: Optional[str] = None,
    paid: Optional[bool] = None,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> List[BillRead]:
    """Filter bills by reservation or paid status."""
    stmt = select(Bill)
    if reservation_id is not None:
        stmt = stmt.where(Bill.reservation_id == reservation_id)
    if paid is not None:
        stmt = stmt.where(Bill.paid == paid)

    bills = (await session.exec(stmt)).all()
    return [BillRead.model_validate(b) for b in bills]


@router.get("/{bill_id}", response_model=BillRead, summary="Get bill by ID")
async def get_bill(
    bill_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BillRead:
    """Retrieve a single bill with all line items."""
    bill = await session.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return BillRead.model_validate(bill)


@router.post("/{bill_id}/paid", response_model=BillRead, summary="Mark bill as paid")
async def mark_paid(
    bill_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BillRead:
    """Mark bill paid. Records paid_datetime and paid_confirmed_by (staff username from JWT)."""
    bill = await session.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    bill.paid = True
    bill.paid_datetime = datetime.now(timezone.utc)
    bill.paid_confirmed_by = username
    bill.updated_at = datetime.now(timezone.utc)

    session.add(bill)
    await session.commit()
    await session.refresh(bill)

    return BillRead.model_validate(bill)


@router.post("/{bill_id}/discount", response_model=BillRead, summary="Apply discount to line item")
async def apply_discount(
    bill_id: str,
    body: ApplyDiscountRequest,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BillRead:
    """Apply a staff discount to a specific line item. Records discount_applied_by."""
    bill = await session.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    bill_dict = bill.model_dump()
    try:
        updated_dict = billing_svc.apply_discount(
            bill_dict, body.line_item_id, body.discount_amount, username
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    bill.line_items = updated_dict["line_items"]
    bill.total_discounts = updated_dict["total_discounts"]
    bill.total_due = updated_dict["total_due"]
    bill.updated_at = datetime.now(timezone.utc)
    flag_modified(bill, "line_items")

    session.add(bill)
    await session.commit()
    await session.refresh(bill)

    return BillRead.model_validate(bill)


@router.get("/{bill_id}/receipt", summary="Get or generate PDF receipt")
async def get_receipt(
    bill_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Return PDF receipt. Generates if not yet generated. Uses business.json branding."""
    bill = await session.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    reservation = await session.get(Reservation, bill.reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    dog = await session.get(Dog, reservation.dog_id)
    if not dog:
        raise HTTPException(status_code=404, detail="Dog not found")

    owner = await session.get(Owner, dog.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    bill_dict = bill.model_dump()
    owner_dict = owner.model_dump()
    owner_dict["name"] = f"{owner.first_name} {owner.last_name}"
    dog_dict = dog.model_dump()
    reservation_dict = reservation.model_dump()

    pdf_path = await pdf_svc.generate_receipt(bill_dict, owner_dict, dog_dict, reservation_dict)

    if not pdf_path:
        raise HTTPException(status_code=500, detail="PDF generation failed")

    # Persist the receipt path
    bill.receipt_pdf_path = pdf_path
    bill.updated_at = datetime.now(timezone.utc)
    session.add(bill)
    await session.commit()

    return FileResponse(pdf_path, media_type="application/pdf", filename=f"receipt_{bill_id}.pdf")


@router.post("/{bill_id}/email-receipt", response_model=BillRead, summary="Email receipt to owner")
async def email_receipt(
    bill_id: str,
    username: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BillRead:
    """Send PDF receipt to owner email via SMTP. Sets receipt_emailed=true."""
    bill = await session.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    reservation = await session.get(Reservation, bill.reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    dog = await session.get(Dog, reservation.dog_id)
    if not dog:
        raise HTTPException(status_code=404, detail="Dog not found")

    owner = await session.get(Owner, dog.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    bill_dict = bill.model_dump()
    owner_dict = owner.model_dump()
    owner_dict["name"] = f"{owner.first_name} {owner.last_name}"
    dog_dict = dog.model_dump()
    reservation_dict = reservation.model_dump()

    pdf_path = await pdf_svc.generate_receipt(bill_dict, owner_dict, dog_dict, reservation_dict)
    if not pdf_path:
        raise HTTPException(status_code=500, detail="PDF generation failed")

    owner_name = f"{owner.first_name} {owner.last_name}"
    success = await email_svc.send_receipt(owner.email, owner_name, pdf_path)

    if success:
        bill.receipt_emailed = True

    bill.receipt_pdf_path = pdf_path
    bill.updated_at = datetime.now(timezone.utc)
    session.add(bill)
    await session.commit()
    await session.refresh(bill)

    return BillRead.model_validate(bill)
