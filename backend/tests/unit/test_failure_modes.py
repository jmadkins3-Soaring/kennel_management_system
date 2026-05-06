"""Unit tests: failure modes — out-of-bounds inputs, invalid values.

Spec §11.1 — Failure mode tests:
  - Negative prices
  - Invalid dates
  - Oversized strings (exceed field max_length)
  - Null required fields
  - Invalid enum values
"""

import pytest
from datetime import date
from pydantic import ValidationError

from app.models.owner import OwnerCreate
from app.models.dog import DogCreate, SizeClass, MedicalStatus
from app.models.bill import BillLineItem, LineItemType
from app.models.incident import IncidentCreate, IncidentType
from app.models.reservation import ReservationCreate


# ── Owner validation ───────────────────────────────────────────────────────────

def test_owner_create_requires_first_name():
    with pytest.raises(ValidationError):
        OwnerCreate(last_name="Smith", phone_number="303-555-0100", email="a@b.com")


def test_owner_create_requires_last_name():
    with pytest.raises(ValidationError):
        OwnerCreate(first_name="Jane", phone_number="303-555-0100", email="a@b.com")


def test_owner_create_requires_email():
    with pytest.raises(ValidationError):
        OwnerCreate(first_name="Jane", last_name="Smith", phone_number="303-555-0100")


def test_owner_first_name_max_length():
    with pytest.raises(ValidationError):
        OwnerCreate(first_name="A" * 51, last_name="Smith", phone_number="303-555-0100", email="a@b.com")


def test_owner_last_name_max_length():
    with pytest.raises(ValidationError):
        OwnerCreate(first_name="Jane", last_name="B" * 51, phone_number="303-555-0100", email="a@b.com")


# ── Dog validation ─────────────────────────────────────────────────────────────

def test_dog_invalid_size_class():
    with pytest.raises(ValidationError):
        DogCreate(
            owner_id="owner-1",
            name="Rex",
            breed="Lab",
            size_class="XXL",  # invalid
            medical_status="Healthy",
        )


def test_dog_invalid_medical_status():
    with pytest.raises(ValidationError):
        DogCreate(
            owner_id="owner-1",
            name="Rex",
            breed="Lab",
            size_class="M",
            medical_status="Fine",  # invalid enum
        )


def test_dog_requires_owner_id():
    with pytest.raises(ValidationError):
        DogCreate(name="Rex", breed="Lab", size_class="M", medical_status="Healthy")


def test_dog_name_max_length():
    with pytest.raises(ValidationError):
        DogCreate(
            owner_id="owner-1",
            name="R" * 51,
            breed="Lab",
            size_class="M",
            medical_status="Healthy",
        )


# ── Bill line item validation ──────────────────────────────────────────────────

def test_bill_line_item_invalid_type():
    with pytest.raises(ValidationError):
        BillLineItem(
            type="InvalidType",
            description="Test",
            unit_price=10.00,
            quantity=1,
            amount=10.00,
        )


# ── Incident validation ────────────────────────────────────────────────────────

def test_incident_invalid_type():
    with pytest.raises(ValidationError):
        IncidentCreate(
            dog_id="d1",
            reservation_id="r1",
            incident_type="WrongType",
            description="test",
            occurred_datetime="2026-05-05T10:00:00",
        )


def test_incident_requires_description():
    with pytest.raises(ValidationError):
        IncidentCreate(
            dog_id="d1",
            reservation_id="r1",
            incident_type="Behavioral",
            occurred_datetime="2026-05-05T10:00:00",
        )


# ── Billing: negative prices ───────────────────────────────────────────────────

def test_billing_rejects_negative_discount():
    from app.services.billing import apply_discount
    bill = {
        "line_items": [{"line_item_id": "li-1", "amount": 50.00, "discount": 0.0}],
        "subtotal": 50.00,
        "total_discounts": 0.0,
        "total_due": 50.00,
    }
    with pytest.raises(ValueError):
        apply_discount(bill, "li-1", discount_amount=-5.00, applied_by="staff1")


# ── PACFA: invalid inputs ──────────────────────────────────────────────────────

def test_pacfa_rejects_zero_stay_days():
    from app.services.pacfa import required_sqft
    with pytest.raises(ValueError):
        required_sqft("M", stay_days=0)


def test_pacfa_rejects_negative_stay_days():
    from app.services.pacfa import required_sqft
    with pytest.raises(ValueError):
        required_sqft("M", stay_days=-1)
