"""IAT: Bills — list, get, mark paid, apply discount, receipt, email receipt."""

import pytest
from unittest.mock import patch, AsyncMock
from .conftest import create_owner, create_dog, create_reservation, get_first_large_kennel


async def _checked_out_bill(client, headers):
    """Create a reservation, check in, check out, and return the resulting bill."""
    owner = await create_owner(client, headers)
    dog = await create_dog(client, headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(client, headers)
    res = await create_reservation(client, headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")
    await client.post(f"/api/reservations/{res['reservation_id']}/checkin",
                      json={"medical_acknowledged": False}, headers=headers)
    await client.post(f"/api/reservations/{res['reservation_id']}/checkout",
                      json={"checkout_healthy": True}, headers=headers)

    r = await client.get(f"/api/bills?reservation_id={res['reservation_id']}", headers=headers)
    bills = r.json()
    assert len(bills) >= 1, "Expected at least one bill after checkout"
    return bills[0], res


@pytest.mark.asyncio
async def test_list_bills_empty(iat_client, iat_headers):
    r = await iat_client.get("/api/bills", headers=iat_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_bills_after_checkin(iat_client, iat_headers):
    owner = await create_owner(iat_client, iat_headers)
    dog = await create_dog(iat_client, iat_headers, owner_id=owner["owner_id"])
    kennel = await get_first_large_kennel(iat_client, iat_headers)
    res = await create_reservation(iat_client, iat_headers,
        dog_id=dog["dog_id"], kennel_id=kennel["kennel_id"],
        dropoff="2026-06-10T09:00:00", pickup="2026-06-13T10:00:00")
    await iat_client.post(f"/api/reservations/{res['reservation_id']}/checkin",
                          json={"medical_acknowledged": False}, headers=iat_headers)
    r = await iat_client.get(
        f"/api/bills?reservation_id={res['reservation_id']}", headers=iat_headers
    )
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_list_bills_filter_unpaid(iat_client, iat_headers):
    await _checked_out_bill(iat_client, iat_headers)
    r = await iat_client.get("/api/bills?paid=false", headers=iat_headers)
    assert r.status_code == 200
    assert all(not b["paid"] for b in r.json())


@pytest.mark.asyncio
async def test_get_bill_by_id(iat_client, iat_headers):
    bill, _ = await _checked_out_bill(iat_client, iat_headers)
    r = await iat_client.get(f"/api/bills/{bill['bill_id']}", headers=iat_headers)
    assert r.status_code == 200
    assert r.json()["bill_id"] == bill["bill_id"]


@pytest.mark.asyncio
async def test_get_bill_not_found(iat_client, iat_headers):
    r = await iat_client.get("/api/bills/no-such-id", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_mark_bill_paid(iat_client, iat_headers):
    bill, _ = await _checked_out_bill(iat_client, iat_headers)
    r = await iat_client.post(f"/api/bills/{bill['bill_id']}/paid", headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["paid"] is True
    assert data["paid_confirmed_by"] == "iat_staff"
    assert data["paid_datetime"] is not None


@pytest.mark.asyncio
async def test_mark_paid_not_found(iat_client, iat_headers):
    r = await iat_client.post("/api/bills/no-such-id/paid", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_apply_discount_to_line_item(iat_client, iat_headers):
    bill, _ = await _checked_out_bill(iat_client, iat_headers)
    line_item_id = bill["line_items"][0]["line_item_id"]
    original_due = bill["total_due"]

    r = await iat_client.post(f"/api/bills/{bill['bill_id']}/discount", json={
        "line_item_id": line_item_id,
        "discount_amount": 10.00,
    }, headers=iat_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total_discounts"] == 10.00
    assert data["total_due"] == pytest.approx(original_due - 10.00)


@pytest.mark.asyncio
async def test_apply_discount_invalid_line_item(iat_client, iat_headers):
    bill, _ = await _checked_out_bill(iat_client, iat_headers)
    r = await iat_client.post(f"/api/bills/{bill['bill_id']}/discount", json={
        "line_item_id": "no-such-line-item",
        "discount_amount": 5.00,
    }, headers=iat_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_apply_discount_exceeds_amount(iat_client, iat_headers):
    bill, _ = await _checked_out_bill(iat_client, iat_headers)
    line_item_id = bill["line_items"][0]["line_item_id"]
    r = await iat_client.post(f"/api/bills/{bill['bill_id']}/discount", json={
        "line_item_id": line_item_id,
        "discount_amount": 99999.00,
    }, headers=iat_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_apply_discount_bill_not_found(iat_client, iat_headers):
    r = await iat_client.post("/api/bills/no-such-id/discount", json={
        "line_item_id": "x",
        "discount_amount": 5.00,
    }, headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_receipt_returns_pdf(iat_client, iat_headers):
    bill, _ = await _checked_out_bill(iat_client, iat_headers)
    r = await iat_client.get(f"/api/bills/{bill['bill_id']}/receipt", headers=iat_headers)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")


@pytest.mark.asyncio
async def test_get_receipt_bill_not_found(iat_client, iat_headers):
    r = await iat_client.get("/api/bills/no-such-id/receipt", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_email_receipt(iat_client, iat_headers):
    bill, _ = await _checked_out_bill(iat_client, iat_headers)
    with patch("app.services.email.send_receipt", new_callable=AsyncMock, return_value=True):
        r = await iat_client.post(
            f"/api/bills/{bill['bill_id']}/email-receipt", headers=iat_headers
        )
    assert r.status_code == 200
    assert r.json()["receipt_emailed"] is True


@pytest.mark.asyncio
async def test_email_receipt_bill_not_found(iat_client, iat_headers):
    r = await iat_client.post("/api/bills/no-such-id/email-receipt", headers=iat_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_bills_filter_paid(iat_client, iat_headers):
    bill, _ = await _checked_out_bill(iat_client, iat_headers)
    await iat_client.post(f"/api/bills/{bill['bill_id']}/paid", headers=iat_headers)
    r = await iat_client.get("/api/bills?paid=true", headers=iat_headers)
    assert r.status_code == 200
    assert all(b["paid"] for b in r.json())
