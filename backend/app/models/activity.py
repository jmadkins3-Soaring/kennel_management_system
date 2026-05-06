"""Activity domain model. billable only when performed_datetime and performed_by are set."""

from datetime import datetime, date, timezone
from typing import Optional
import uuid

from sqlmodel import Field, SQLModel


class ActivityBase(SQLModel):
    reservation_id: str = Field(foreign_key="reservations.reservation_id", index=True)
    activity_type: str = Field(max_length=100)
    scheduled_date: date
    notes: Optional[str] = None


class Activity(ActivityBase, table=True):
    __tablename__ = "activities"

    activity_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    incident_id: Optional[str] = Field(default=None, foreign_key="incidents.incident_id")
    performed_datetime: Optional[datetime] = None
    performed_by: Optional[str] = Field(default=None, max_length=50)
    qualifies_for_pacfa_exception: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def billable(self) -> bool:
        return self.performed_datetime is not None and self.performed_by is not None


class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(SQLModel):
    scheduled_date: Optional[date] = None
    notes: Optional[str] = None


class CompleteActivityRequest(SQLModel):
    performed_datetime: datetime
    notes: Optional[str] = None


class ActivityRead(ActivityBase):
    activity_id: str
    incident_id: Optional[str] = None
    performed_datetime: Optional[datetime] = None
    performed_by: Optional[str] = None
    billable: bool = False
    qualifies_for_pacfa_exception: bool
    created_at: datetime
