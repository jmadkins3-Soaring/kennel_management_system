"""Reservation domain model. Phase fields are computed, not stored."""

from datetime import datetime, timezone
from typing import Optional, List, Any
from enum import Enum
import uuid

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON


class Phase(str, Enum):
    MORNING = "Morning"
    AFTERNOON = "Afternoon"
    EVENING = "Evening"
    NIGHT = "Night"


class OverrideEvent(SQLModel):
    """Pydantic-only sub-object stored in override_log JSON column."""
    override_type: str  # PhaseConflict | OpenEndedPickup | SizeWarning | UnpaidBill
    override_datetime: datetime
    override_by: str
    conflict_description: str


class ReservationBase(SQLModel):
    dog_id: str = Field(foreign_key="dogs.dog_id", index=True)
    kennel_id: str = Field(foreign_key="kennels.kennel_id", index=True)
    dropoff_datetime: datetime
    pickup_datetime: Optional[datetime] = None
    pickup_open_ended: bool = Field(default=False)
    notes: Optional[str] = None


class Reservation(ReservationBase, table=True):
    __tablename__ = "reservations"

    reservation_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    checkin_datetime: Optional[datetime] = None
    checkout_datetime: Optional[datetime] = None
    checkin_staff: Optional[str] = Field(default=None, max_length=50)
    checkout_staff: Optional[str] = Field(default=None, max_length=50)
    medical_acknowledged: bool = Field(default=False)
    checkout_healthy: Optional[bool] = None
    checkout_notes: Optional[str] = None
    pickup_overdue_alerted: bool = Field(default=False)
    cancelled: bool = Field(default=False)
    cancel_requested_by: Optional[str] = Field(default=None, max_length=20)  # Staff | Owner
    cancel_confirmed_by: Optional[str] = Field(default=None, max_length=50)
    override_log: Optional[List[Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReservationCreate(ReservationBase):
    prescheduled_activities: Optional[List[dict]] = None  # [{activity_type, scheduled_date}]


class ReservationUpdate(SQLModel):
    dropoff_datetime: Optional[datetime] = None
    pickup_datetime: Optional[datetime] = None
    pickup_open_ended: Optional[bool] = None
    kennel_id: Optional[str] = None
    notes: Optional[str] = None


class CheckInRequest(SQLModel):
    medical_acknowledged: bool = False
    override_unpaid_bill: bool = False


class CheckOutRequest(SQLModel):
    checkout_healthy: bool
    checkout_notes: Optional[str] = None


class ReservationRead(ReservationBase):
    reservation_id: str
    dropoff_phase: Optional[Phase] = None   # computed
    pickup_phase: Optional[Phase] = None    # computed
    stay_duration_days: Optional[int] = None  # computed
    checkin_datetime: Optional[datetime] = None
    checkout_datetime: Optional[datetime] = None
    checkin_staff: Optional[str] = None
    checkout_staff: Optional[str] = None
    medical_acknowledged: bool
    checkout_healthy: Optional[bool] = None
    checkout_notes: Optional[str] = None
    pickup_overdue_alerted: bool
    cancelled: bool
    cancel_requested_by: Optional[str] = None
    cancel_confirmed_by: Optional[str] = None
    override_log: Optional[List[Any]] = None
    created_at: datetime
    updated_at: datetime
