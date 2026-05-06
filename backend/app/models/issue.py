"""Issue Report domain model (kennel maintenance/safety issues)."""

from datetime import datetime, timezone
from typing import Optional
from enum import Enum
import uuid

from sqlmodel import Field, SQLModel


class IssueType(str, Enum):
    MAINTENANCE = "Maintenance"
    SAFETY = "Safety"
    CLEANLINESS = "Cleanliness"
    EQUIPMENT = "Equipment"
    OTHER = "Other"


class IssueBase(SQLModel):
    kennel_id: str = Field(foreign_key="kennels.kennel_id", index=True)
    issue_type: IssueType
    description: str
    reported_datetime: datetime


class Issue(IssueBase, table=True):
    __tablename__ = "issues"

    issue_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    reported_by: str = Field(max_length=50)
    resolved: bool = Field(default=False)
    resolved_datetime: Optional[datetime] = None
    resolved_by: Optional[str] = Field(default=None, max_length=50)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IssueCreate(IssueBase):
    pass


class ResolveIssueRequest(SQLModel):
    resolution_notes: Optional[str] = None


class IssueRead(IssueBase):
    issue_id: str
    reported_by: str
    resolved: bool
    resolved_datetime: Optional[datetime] = None
    resolved_by: Optional[str] = None
    created_at: datetime
