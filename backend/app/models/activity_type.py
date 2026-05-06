"""ActivityType — UI-managed reference data, prices in pricing.json."""

from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlmodel import Field, SQLModel


class ActivityTypeBase(SQLModel):
    name: str = Field(max_length=100, unique=True)
    qualifies_for_pacfa_exception: bool = Field(default=False)
    active: bool = Field(default=True)


class ActivityType(ActivityTypeBase, table=True):
    __tablename__ = "activity_types"

    activity_type_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ActivityTypeCreate(SQLModel):
    name: str = Field(max_length=100)
    qualifies_for_pacfa_exception: bool = False


class ActivityTypeUpdate(SQLModel):
    active: Optional[bool] = None
    qualifies_for_pacfa_exception: Optional[bool] = None
