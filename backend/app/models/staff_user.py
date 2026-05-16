"""Staff user model."""

from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlmodel import Field, SQLModel


class StaffUser(SQLModel, table=True):
    __tablename__ = "staff_users"

    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    username: str = Field(max_length=50, unique=True, index=True)
    password_hash: str
    role: str = Field(default="staff")  # "admin" | "staff"
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
