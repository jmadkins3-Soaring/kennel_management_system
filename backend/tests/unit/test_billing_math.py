"""Unit tests: billing math — line items, discounts, totals, 14-day cycles.

Spec §5.5 — total_due = (unit_price × quantity) - discount per line item
             total_due = subtotal - total_discounts
Spec §6.8 — 14-day extended stay billing cycle detection
"""

import pytest
from datetime import date, timedelta
from app.services.billing import generate_bill, apply_discount, check_14day_cycle


# ── Line item total calculation ────────────────────────────────────────────────

def test_kennel_stay_line_item_math():
    """3 nights at flat rate (60.00/night) = 180.00."""
    bill = generate_bill(
        reservation_id="res-001",
        cycle_start=date(2026, 5, 1),
        cycle_end=date(2026, 5, 3),
        size_class="L",
        activities=[],
    )
    stay_item = next(i for i in bill["line_items"] if i["type"] == "KennelStay")
    assert stay_item["unit_price"] == pytest.approx(60.00)
    assert stay_item["quantity"] == 3
    assert stay_item["amount"] == pytest.approx(180.00)


def test_activity_line_item_math():
    """2 Nature Walks at 10.00 each = 20.00."""
    activities = [
        {"activity_type": "Nature Walk", "performed_datetime": "2026-05-01T10:00:00", "performed_by": "staff1"},
        {"activity_type": "Nature Walk", "performed_datetime": "2026-05-02T10:00:00", "performed_by": "staff1"},
    ]
    bill = generate_bill(
        reservation_id="res-001",
        cycle_start=date(2026, 5, 1),
        cycle_end=date(2026, 5, 2),
        size_class="S",
        activities=activities,
    )
    activity_items = [i for i in bill["line_items"] if i["type"] == "Activity"]
    total = sum(i["amount"] for i in activity_items)
    assert total == pytest.approx(20.00)


def test_unperformed_activity_not_billed():
    """Activity without performed_datetime must NOT appear as a billable line item."""
    activities = [
        {"activity_type": "Nature Walk", "performed_datetime": None, "performed_by": None},
    ]
    bill = generate_bill(
        reservation_id="res-001",
        cycle_start=date(2026, 5, 1),
        cycle_end=date(2026, 5, 1),
        size_class="S",
        activities=activities,
    )
    billable_activities = [i for i in bill["line_items"] if i["type"] == "Activity"]
    assert len(billable_activities) == 0


def test_subtotal_is_sum_of_line_items():
    bill = generate_bill(
        reservation_id="res-001",
        cycle_start=date(2026, 5, 1),
        cycle_end=date(2026, 5, 2),
        size_class="M",
        activities=[
            {"activity_type": "Playtime", "performed_datetime": "2026-05-01T14:00:00", "performed_by": "staff1"},
        ],
    )
    expected_subtotal = sum(i["amount"] for i in bill["line_items"])
    assert bill["subtotal"] == pytest.approx(expected_subtotal)


def test_total_due_equals_subtotal_minus_discounts():
    bill = generate_bill(
        reservation_id="res-001",
        cycle_start=date(2026, 5, 1),
        cycle_end=date(2026, 5, 3),
        size_class="M",
        activities=[],
    )
    assert bill["total_discounts"] == pytest.approx(0.0)
    assert bill["total_due"] == pytest.approx(bill["subtotal"])


# ── Discount application ───────────────────────────────────────────────────────

def test_apply_discount_reduces_total_due():
    bill = generate_bill("r1", date(2026, 5, 1), date(2026, 5, 2), "M", [])
    line_item_id = bill["line_items"][0]["line_item_id"]
    original_due = bill["total_due"]

    updated = apply_discount(bill, line_item_id, discount_amount=10.00, applied_by="staff1")
    assert updated["total_discounts"] == pytest.approx(10.00)
    assert updated["total_due"] == pytest.approx(original_due - 10.00)


def test_apply_discount_records_applied_by():
    bill = generate_bill("r1", date(2026, 5, 1), date(2026, 5, 2), "L", [])
    line_item_id = bill["line_items"][0]["line_item_id"]
    updated = apply_discount(bill, line_item_id, discount_amount=5.00, applied_by="manager")
    discounted_item = next(i for i in updated["line_items"] if i["line_item_id"] == line_item_id)
    assert discounted_item["discount_applied_by"] == "manager"
    assert discounted_item["discount"] == pytest.approx(5.00)


def test_discount_cannot_exceed_line_item_amount():
    """Discount larger than the line item amount must be rejected."""
    bill = generate_bill("r1", date(2026, 5, 1), date(2026, 5, 1), "XS", [])
    line_item_id = bill["line_items"][0]["line_item_id"]
    line_amount = bill["line_items"][0]["amount"]
    with pytest.raises(ValueError):
        apply_discount(bill, line_item_id, discount_amount=line_amount + 1, applied_by="staff1")


# ── 14-day cycle detection ─────────────────────────────────────────────────────

def test_14day_cycle_triggers_on_14th_day():
    checkin = date(2026, 5, 1)
    today = checkin + timedelta(days=14)
    assert check_14day_cycle("res-001", checkin, today) is True


def test_14day_cycle_does_not_trigger_early():
    checkin = date(2026, 5, 1)
    today = checkin + timedelta(days=13)
    assert check_14day_cycle("res-001", checkin, today) is False


def test_14day_cycle_triggers_on_28th_day():
    checkin = date(2026, 5, 1)
    today = checkin + timedelta(days=28)
    assert check_14day_cycle("res-001", checkin, today) is True


def test_14day_cycle_does_not_trigger_on_15th_day():
    checkin = date(2026, 5, 1)
    today = checkin + timedelta(days=15)
    assert check_14day_cycle("res-001", checkin, today) is False


def test_short_stay_never_triggers_14day_cycle():
    checkin = date(2026, 5, 1)
    for days in range(1, 14):
        assert check_14day_cycle("res-001", checkin, checkin + timedelta(days=days)) is False
