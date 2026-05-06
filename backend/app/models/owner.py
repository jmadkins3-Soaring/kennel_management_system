"""Owner domain model."""

from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlmodel import Field, SQLModel


class OwnerBase(SQLModel):
    first_name: str = Field(max_length=50)
    last_name: str = Field(max_length=50, index=True)
    alternate_name: Optional[str] = Field(default=None, max_length=100)
    phone_number: str = Field(max_length=20)
    sms_number: Optional[str] = Field(default=None, max_length=20)
    email: str = Field(max_length=100)
    emergency_contact_name: Optional[str] = Field(default=None, max_length=100)
    emergency_contact_phone: Optional[str] = Field(default=None, max_length=20)
    vet_name: Optional[str] = Field(default=None, max_length=100)
    vet_phone: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = Field(default=None)


class Owner(OwnerBase, table=True):
    __tablename__ = "owners"

    owner_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    archived: bool = Field(default=False)


class OwnerCreate(OwnerBase):
    pass


class OwnerUpdate(SQLModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    alternate_name: Optional[str] = None
    phone_number: Optional[str] = None
    sms_number: Optional[str] = None
    email: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    vet_name: Optional[str] = None
    vet_phone: Optional[str] = None
    notes: Optional[str] = None


class OwnerRead(OwnerBase):
    owner_id: str
    created_at: datetime
    updated_at: datetime
    archived: bool
