"""Manual admin hold on a kennel (separate from automatic post-checkout holds)."""

from datetime import datetime, date, timezone
from typing import Optional
import uuid

from sqlmodel import Field, SQLModel


class KennelHold(SQLModel, table=True):
    __tablename__ = "kennel_holds"

    hold_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    kennel_id: str = Field(foreign_key="kennels.kennel_id", index=True)
    start_date: date
    end_date: date
    reason: Optional[str] = Field(default=None, max_length=255)
    created_by: str = Field(max_length=50)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    released_at: Optional[datetime] = None
    released_by: Optional[str] = Field(default=None, max_length=50)
    active: bool = Field(default=True)


class KennelHoldCreate(SQLModel):
    kennel_id: str
    start_date: date
    end_date: date
    reason: Optional[str] = None
