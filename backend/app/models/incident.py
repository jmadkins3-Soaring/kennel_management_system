"""Incident Report domain model."""

from datetime import datetime, timezone
from typing import Optional
from enum import Enum
import uuid

from pydantic import ConfigDict
from sqlalchemy import Column, String as SAString
from sqlmodel import Field, SQLModel


class IncidentType(str, Enum):
    BEHAVIORAL = "Behavioral"
    INJURY = "Injury"
    MEDICAL = "Medical"
    ESCAPE_ATTEMPT = "EscapeAttempt"
    OTHER = "Other"


class IncidentBase(SQLModel):
    model_config = ConfigDict(use_enum_values=True)

    dog_id: str = Field(foreign_key="dogs.dog_id", index=True)
    reservation_id: str = Field(foreign_key="reservations.reservation_id", index=True)
    incident_type: IncidentType
    description: str
    occurred_datetime: datetime
    visible_to_owner: bool = Field(default=False)
    owner_notified: bool = Field(default=False)


class Incident(IncidentBase, table=True):
    __tablename__ = "incidents"

    incident_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    incident_type: str = Field(sa_column=Column("incident_type", SAString(50)))
    reported_by: str = Field(max_length=50)
    resolved: bool = Field(default=False)
    resolved_datetime: Optional[datetime] = None
    resolved_by: Optional[str] = Field(default=None, max_length=50)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncidentCreate(IncidentBase):
    pass


class ResolveIncidentRequest(SQLModel):
    resolution_notes: Optional[str] = None


class IncidentRead(IncidentBase):
    incident_id: str
    reported_by: str
    resolved: bool
    resolved_datetime: Optional[datetime] = None
    resolved_by: Optional[str] = None
    created_at: datetime
