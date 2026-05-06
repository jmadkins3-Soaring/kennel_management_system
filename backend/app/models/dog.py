"""Dog domain model. vaccination_records stored as JSON array."""

from datetime import datetime, date, timezone
from typing import Optional, List, Any
from enum import Enum
import uuid

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON, String as SAString


class SizeClass(str, Enum):
    XS = "XS"
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"


class MedicalStatus(str, Enum):
    HEALTHY = "Healthy"
    INJURED = "Injured"
    QUARANTINE = "Quarantine"
    ON_MEDICATION = "On Medication"
    OTHER = "Other"


class VaccinationRecord(SQLModel):
    """Pydantic-only sub-object stored in JSON column."""
    vaccine_name: str = Field(max_length=100)
    administered_date: date
    expiration_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=255)


class DogBase(SQLModel):
    model_config = ConfigDict(use_enum_values=True)

    owner_id: str = Field(foreign_key="owners.owner_id", index=True)
    name: str = Field(max_length=50)
    breed: str = Field(max_length=100)
    description: Optional[str] = None
    size_class: SizeClass
    weight_lbs: Optional[float] = None
    date_of_birth: Optional[date] = None
    medical_status: MedicalStatus = Field(default=MedicalStatus.HEALTHY)
    medical_notes: Optional[str] = None
    photo_url: Optional[str] = None
    notes: Optional[str] = None


class Dog(DogBase, table=True):
    __tablename__ = "dogs"

    dog_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    medical_status: str = Field(default="Healthy", sa_column=Column("medical_status", SAString(50), default="Healthy"))
    vaccination_records: Optional[List[Any]] = Field(
        default=None, sa_column=Column(JSON)
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    archived: bool = Field(default=False)


class DogCreate(DogBase):
    vaccination_records: Optional[List[VaccinationRecord]] = None


class DogUpdate(SQLModel):
    name: Optional[str] = None
    breed: Optional[str] = None
    description: Optional[str] = None
    size_class: Optional[SizeClass] = None
    weight_lbs: Optional[float] = None
    date_of_birth: Optional[date] = None
    medical_status: Optional[MedicalStatus] = None
    medical_notes: Optional[str] = None
    photo_url: Optional[str] = None
    notes: Optional[str] = None
    vaccination_records: Optional[List[VaccinationRecord]] = None


class DogRead(DogBase):
    dog_id: str
    vaccination_records: Optional[List[Any]] = None
    open_incidents: bool = False  # computed by route from incidents table
    created_at: datetime
    updated_at: datetime
    archived: bool
