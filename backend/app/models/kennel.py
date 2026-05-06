"""Kennel domain model. Provisioned from kennels.json on startup."""

from datetime import datetime, timezone
from typing import Optional
from enum import Enum
import uuid

from sqlmodel import Field, SQLModel


class SizeClass(str, Enum):
    XS = "XS"
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"


class KennelStatus(str, Enum):
    FREE = "Free"
    HOLD = "Hold"
    ASSIGNED = "Assigned"
    USED = "Used"


class KennelBase(SQLModel):
    kennel_number: str = Field(max_length=20, unique=True, index=True)
    kennel_type: str = Field(max_length=50)
    max_size_class: SizeClass
    sqft: float
    features: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    active: bool = Field(default=True)
    provisioned_from_config: bool = Field(default=False)


class Kennel(KennelBase, table=True):
    __tablename__ = "kennels"

    kennel_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KennelUpdate(SQLModel):
    description: Optional[str] = None
    active: Optional[bool] = None
    features: Optional[str] = None


class KennelRead(KennelBase):
    kennel_id: str
    created_at: datetime
    current_status: Optional[KennelStatus] = None  # injected by route for requested date/phase
