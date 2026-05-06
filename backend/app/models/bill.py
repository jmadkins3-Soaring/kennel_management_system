"""Bill domain model. line_items stored as JSON array."""

from datetime import datetime, date, timezone
from typing import Optional, List, Any
from enum import Enum
import uuid

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON


class LineItemType(str, Enum):
    KENNEL_STAY = "KennelStay"
    ACTIVITY = "Activity"
    ADDITIONAL_CHARGE = "AdditionalCharge"


class BillLineItem(SQLModel):
    """Pydantic-only sub-object stored in line_items JSON column."""
    line_item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: LineItemType
    description: str = Field(max_length=255)
    unit_price: float
    quantity: float
    discount: float = 0.0
    discount_applied_by: Optional[str] = None
    amount: float  # (unit_price * quantity) - discount
    activity_id: Optional[str] = None


class Bill(SQLModel, table=True):
    __tablename__ = "bills"

    bill_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    reservation_id: str = Field(foreign_key="reservations.reservation_id", index=True)
    billing_cycle: int = Field(default=1)
    cycle_start_date: date
    cycle_end_date: date
    line_items: Optional[List[Any]] = Field(default=None, sa_column=Column(JSON))
    subtotal: float = Field(default=0.0)
    total_discounts: float = Field(default=0.0)
    total_due: float = Field(default=0.0)
    paid: bool = Field(default=False)
    paid_datetime: Optional[datetime] = None
    paid_confirmed_by: Optional[str] = Field(default=None, max_length=50)
    receipt_emailed: bool = Field(default=False)
    receipt_pdf_path: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BillRead(SQLModel):
    bill_id: str
    reservation_id: str
    billing_cycle: int
    cycle_start_date: date
    cycle_end_date: date
    line_items: Optional[List[Any]] = None
    subtotal: float
    total_discounts: float
    total_due: float
    paid: bool
    paid_datetime: Optional[datetime] = None
    paid_confirmed_by: Optional[str] = None
    receipt_emailed: bool
    receipt_pdf_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MarkPaidRequest(SQLModel):
    pass  # staff username comes from JWT


class ApplyDiscountRequest(SQLModel):
    line_item_id: str
    discount_amount: float
