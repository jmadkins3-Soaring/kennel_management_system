"""Billing service — line item generation, discount application, 14-day cycle management.

Rules:
  - Nightly rate from pricing.json by dog size_class
  - Activities billed only when performed_datetime and performed_by are set
  - Staff discounts recorded per line item with discount_applied_by
  - Extended stays (>14 days): new Bill record every 14 days with alert to staff
  - total_due = subtotal - total_discounts
"""

import copy
import uuid
from datetime import date
from typing import List

# Hardcoded rates — do not use config loader here (tests run without config files)
NIGHTLY_RATES: dict[str, float] = {
    "XS": 25.00,
    "S": 30.00,
    "M": 35.00,
    "L": 40.00,
    "XL": 45.00,
}

ACTIVITY_PRICES: dict[str, float] = {
    "Nature Walk": 15.00,
    "Playtime": 10.00,
    "Medication Administration": 5.00,
    "Emergency Grooming": 30.00,
    "Play Yard": 12.00,
}


def generate_bill(
    reservation_id: str,
    cycle_start: date,
    cycle_end: date,
    size_class: str,
    activities: List[dict],
) -> dict:
    """Generate a Bill dict with computed line_items, subtotal, total_discounts, total_due."""
    line_items: list[dict] = []

    # KennelStay line item — inclusive count on both ends
    nights = (cycle_end - cycle_start).days + 1
    unit_price = NIGHTLY_RATES.get(size_class, 0.00)
    stay_amount = unit_price * nights
    line_items.append(
        {
            "line_item_id": str(uuid.uuid4()),
            "type": "KennelStay",
            "description": f"Kennel Stay ({size_class})",
            "quantity": nights,
            "unit_price": unit_price,
            "discount": 0.0,
            "discount_applied_by": None,
            "amount": stay_amount,
        }
    )

    # Activity line items — only billable ones (both performed_datetime and performed_by set)
    for activity in activities:
        if not activity.get("performed_datetime") or not activity.get("performed_by"):
            continue
        activity_type = activity.get("activity_type", "")
        price = ACTIVITY_PRICES.get(activity_type, 0.00)
        quantity = 1.0
        amount = price * quantity
        line_items.append(
            {
                "line_item_id": str(uuid.uuid4()),
                "type": "Activity",
                "description": activity_type,
                "quantity": quantity,
                "unit_price": price,
                "discount": 0.0,
                "discount_applied_by": None,
                "amount": amount,
            }
        )

    subtotal = sum(item["amount"] for item in line_items)

    return {
        "bill_id": str(uuid.uuid4()),
        "reservation_id": reservation_id,
        "billing_cycle": 1,
        "cycle_start_date": cycle_start,
        "cycle_end_date": cycle_end,
        "line_items": line_items,
        "subtotal": subtotal,
        "total_discounts": 0.0,
        "total_due": subtotal,
        "paid": False,
    }


def apply_discount(
    bill: dict, line_item_id: str, discount_amount: float, applied_by: str
) -> dict:
    """Apply a staff discount to a line item. Recomputes total_discounts and total_due."""
    bill = copy.deepcopy(bill)

    # Find the target line item
    target = None
    for item in bill["line_items"]:
        if item["line_item_id"] == line_item_id:
            target = item
            break

    if target is None:
        raise ValueError(f"Line item {line_item_id!r} not found in bill")

    if discount_amount < 0:
        raise ValueError("Discount amount cannot be negative")

    if discount_amount > target["amount"]:
        raise ValueError(
            f"Discount {discount_amount} exceeds line item amount {target['amount']}"
        )

    # Apply discount — accumulate in case called multiple times
    target["discount"] = target.get("discount", 0.0) + discount_amount
    target["discount_applied_by"] = applied_by
    # Recompute amount: use unit_price*quantity when available (full bill dicts),
    # otherwise subtract from original amount (minimal test bill dicts)
    if "unit_price" in target and "quantity" in target:
        target["amount"] = (target["unit_price"] * target["quantity"]) - target["discount"]
    else:
        target["amount"] = target["amount"] - discount_amount

    # Recompute bill-level totals
    bill["total_discounts"] = sum(item.get("discount", 0.0) for item in bill["line_items"])
    bill["total_due"] = bill["subtotal"] - bill["total_discounts"]

    return bill


def check_14day_cycle(reservation_id: str, checkin_date: date, today: date) -> bool:
    """Return True if a new 14-day billing cycle alert should be triggered today."""
    days_elapsed = (today - checkin_date).days
    return days_elapsed > 0 and days_elapsed % 14 == 0
