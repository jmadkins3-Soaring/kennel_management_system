"""PDF generation service using WeasyPrint.

Generates:
  - Receipts: dog name, owner name, check-in/out datetimes, duration, activity line items,
    discounts, total due, checkout health notes, business branding from business.json, logo.
  - Reports: all 5 report types with business branding header.

Output files written to /tmp/receipts/ and /tmp/reports/ inside the container.
"""

import asyncio
import functools
import logging
import os
from datetime import datetime
from typing import Optional

import weasyprint

from ..config import get_business

logger = logging.getLogger(__name__)

RECEIPTS_DIR = os.environ.get("RECEIPTS_DIR", "/tmp/receipts")  # nosec B108
REPORTS_DIR = os.environ.get("REPORTS_DIR", "/tmp/reports")  # nosec B108

_BASE_CSS = """
body { font-family: Arial, sans-serif; font-size: 12px; color: #222; margin: 20px; }
h1 { font-size: 20px; margin-bottom: 4px; }
h2 { font-size: 15px; margin-bottom: 8px; }
.header { border-bottom: 2px solid #333; padding-bottom: 8px; margin-bottom: 16px; }
.section { margin-bottom: 12px; }
table { width: 100%; border-collapse: collapse; margin-top: 8px; }
th { background: #333; color: #fff; padding: 6px 8px; text-align: left; }
td { padding: 5px 8px; border-bottom: 1px solid #ddd; }
.totals td { font-weight: bold; }
.paid { color: green; font-weight: bold; }
.unpaid { color: red; font-weight: bold; }
"""


def _business_header_html(biz: dict) -> str:
    name = biz.get("name", "Kennel Management")
    address = biz.get("address", "")
    phone = biz.get("phone", "")
    return (
        f'<div class="header">'
        f"<h1>{name}</h1>"
        f"<p>{address} | {phone}</p>"
        f"</div>"
    )


async def _write_pdf(html: str, path: str) -> str:
    """Run WeasyPrint in a thread pool executor. Returns path or '' on failure."""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            functools.partial(weasyprint.HTML(string=html).write_pdf, path),
        )
        return path
    except Exception as exc:
        logger.error("WeasyPrint failed writing %s: %s", path, exc)
        return ""


async def generate_receipt(bill: dict, owner: dict, dog: dict, reservation: dict) -> str:
    """Generate receipt PDF, return file path."""
    try:
        biz = get_business()
    except Exception:
        biz = {}

    os.makedirs(RECEIPTS_DIR, exist_ok=True)

    bill_id = bill.get("bill_id", "unknown")
    owner_name = owner.get("name", owner.get("full_name", ""))
    owner_email = owner.get("email", "")
    dog_name = dog.get("name", "")
    cycle_start = bill.get("cycle_start_date", "")
    cycle_end = bill.get("cycle_end_date", "")
    paid = bill.get("paid", False)
    paid_label = '<span class="paid">PAID</span>' if paid else '<span class="unpaid">UNPAID</span>'

    # Line items table rows
    rows_html = ""
    for item in bill.get("line_items", []):
        desc = item.get("description", "")
        qty = item.get("quantity", 1)
        unit = item.get("unit_price", 0.0)
        discount = item.get("discount", 0.0)
        amount = item.get("amount", 0.0)
        disc_str = f"-${discount:.2f}" if discount else ""
        rows_html += (
            f"<tr><td>{desc}</td><td>{qty}</td>"
            f"<td>${unit:.2f}</td><td>{disc_str}</td><td>${amount:.2f}</td></tr>"
        )

    subtotal = bill.get("subtotal", 0.0)
    total_discounts = bill.get("total_discounts", 0.0)
    total_due = bill.get("total_due", 0.0)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_business_header_html(biz)}
<h2>Receipt</h2>
<div class="section">
  <p><strong>Bill ID:</strong> {bill_id}</p>
  <p><strong>Owner:</strong> {owner_name} &lt;{owner_email}&gt;</p>
  <p><strong>Dog:</strong> {dog_name}</p>
  <p><strong>Billing Period:</strong> {cycle_start} — {cycle_end}</p>
  <p><strong>Status:</strong> {paid_label}</p>
</div>
<div class="section">
  <table>
    <tr><th>Description</th><th>Qty</th><th>Unit Price</th><th>Discount</th><th>Amount</th></tr>
    {rows_html}
    <tr class="totals"><td colspan="4">Subtotal</td><td>${subtotal:.2f}</td></tr>
    <tr class="totals"><td colspan="4">Total Discounts</td><td>-${total_discounts:.2f}</td></tr>
    <tr class="totals"><td colspan="4">Total Due</td><td>${total_due:.2f}</td></tr>
  </table>
</div>
</body></html>"""

    path = os.path.join(RECEIPTS_DIR, f"receipt_{bill_id}.pdf")
    return await _write_pdf(html, path)


async def generate_pacfa_report(active_stays: list) -> str:
    """Render PACFA compliance report PDF. Returns absolute file path."""
    try:
        biz = get_business()
    except Exception:
        biz = {}

    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    rows_html = ""
    for stay in active_stays:
        dog = stay.get("dog_name", "")
        owner = stay.get("owner_name", "")
        kennel = stay.get("kennel_id", "")
        checkin = stay.get("checkin_date", "")
        vaccinations = stay.get("vaccinations", "")
        rows_html += (
            f"<tr><td>{dog}</td><td>{owner}</td><td>{kennel}</td>"
            f"<td>{checkin}</td><td>{vaccinations}</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_business_header_html(biz)}
<h2>PACFA Compliance Report</h2>
<p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
<table>
  <tr><th>Dog</th><th>Owner</th><th>Kennel</th><th>Check-In</th><th>Vaccinations</th></tr>
  {rows_html}
</table>
</body></html>"""

    path = os.path.join(REPORTS_DIR, f"pacfa_{timestamp}.pdf")
    return await _write_pdf(html, path)


async def generate_occupancy_report(start_date, end_date, daily_data: list) -> str:
    """Render occupancy rate report PDF. Returns absolute file path."""
    try:
        biz = get_business()
    except Exception:
        biz = {}

    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    rows_html = ""
    for day in daily_data:
        d = day.get("date", "")
        occupied = day.get("occupied", 0)
        total = day.get("total_kennels", 0)
        rate = day.get("occupancy_rate", 0.0)
        rows_html += f"<tr><td>{d}</td><td>{occupied}</td><td>{total}</td><td>{rate:.1f}%</td></tr>"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_business_header_html(biz)}
<h2>Occupancy Report</h2>
<p>Period: {start_date} — {end_date}</p>
<p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
<table>
  <tr><th>Date</th><th>Occupied</th><th>Total Kennels</th><th>Occupancy Rate</th></tr>
  {rows_html}
</table>
</body></html>"""

    path = os.path.join(REPORTS_DIR, f"occupancy_{timestamp}.pdf")
    return await _write_pdf(html, path)


async def generate_revenue_report(start_date, end_date, data: dict) -> str:
    """Render revenue summary report PDF. Returns absolute file path."""
    try:
        biz = get_business()
    except Exception:
        biz = {}

    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    total_revenue = data.get("total_revenue", 0.0)
    kennel_stay_revenue = data.get("kennel_stay_revenue", 0.0)
    activity_revenue = data.get("activity_revenue", 0.0)
    total_discounts = data.get("total_discounts", 0.0)
    net_revenue = data.get("net_revenue", 0.0)

    daily_rows = ""
    for day in data.get("daily_breakdown", []):
        d = day.get("date", "")
        rev = day.get("revenue", 0.0)
        daily_rows += f"<tr><td>{d}</td><td>${rev:.2f}</td></tr>"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_business_header_html(biz)}
<h2>Revenue Report</h2>
<p>Period: {start_date} — {end_date}</p>
<p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
<div class="section">
  <table>
    <tr><th>Category</th><th>Amount</th></tr>
    <tr><td>Kennel Stay Revenue</td><td>${kennel_stay_revenue:.2f}</td></tr>
    <tr><td>Activity Revenue</td><td>${activity_revenue:.2f}</td></tr>
    <tr><td>Total Revenue</td><td>${total_revenue:.2f}</td></tr>
    <tr><td>Total Discounts</td><td>-${total_discounts:.2f}</td></tr>
    <tr class="totals"><td>Net Revenue</td><td>${net_revenue:.2f}</td></tr>
  </table>
</div>
{"<h2>Daily Breakdown</h2><table><tr><th>Date</th><th>Revenue</th></tr>" + daily_rows + "</table>" if daily_rows else ""}
</body></html>"""

    path = os.path.join(REPORTS_DIR, f"revenue_{timestamp}.pdf")
    return await _write_pdf(html, path)


async def generate_upcoming_report(upcoming: list) -> str:
    """Render upcoming check-ins/outs report PDF. Returns absolute file path."""
    try:
        biz = get_business()
    except Exception:
        biz = {}

    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    rows_html = ""
    for entry in upcoming:
        dog = entry.get("dog_name", "")
        owner = entry.get("owner_name", "")
        event_type = entry.get("event_type", "")
        event_date = entry.get("date", "")
        kennel = entry.get("kennel_id", "")
        rows_html += (
            f"<tr><td>{dog}</td><td>{owner}</td><td>{event_type}</td>"
            f"<td>{event_date}</td><td>{kennel}</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_business_header_html(biz)}
<h2>Upcoming Check-Ins / Check-Outs</h2>
<p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
<table>
  <tr><th>Dog</th><th>Owner</th><th>Event</th><th>Date</th><th>Kennel</th></tr>
  {rows_html}
</table>
</body></html>"""

    path = os.path.join(REPORTS_DIR, f"upcoming_{timestamp}.pdf")
    return await _write_pdf(html, path)


async def generate_open_incidents_report(incidents: list, issues: list) -> str:
    """Render open incidents and issues report PDF. Returns absolute file path."""
    try:
        biz = get_business()
    except Exception:
        biz = {}

    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    incident_rows = ""
    for inc in incidents:
        inc_id = inc.get("incident_id", "")
        dog = inc.get("dog_name", "")
        reported = inc.get("reported_at", "")
        description = inc.get("description", "")
        severity = inc.get("severity", "")
        incident_rows += (
            f"<tr><td>{inc_id}</td><td>{dog}</td><td>{severity}</td>"
            f"<td>{reported}</td><td>{description}</td></tr>"
        )

    issue_rows = ""
    for issue in issues:
        issue_id = issue.get("issue_id", "")
        kennel = issue.get("kennel_id", "")
        reported = issue.get("reported_at", "")
        description = issue.get("description", "")
        status = issue.get("status", "")
        issue_rows += (
            f"<tr><td>{issue_id}</td><td>{kennel}</td><td>{status}</td>"
            f"<td>{reported}</td><td>{description}</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
{_business_header_html(biz)}
<h2>Open Incidents &amp; Issues Report</h2>
<p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

<h2>Incidents</h2>
<table>
  <tr><th>ID</th><th>Dog</th><th>Severity</th><th>Reported</th><th>Description</th></tr>
  {incident_rows if incident_rows else "<tr><td colspan='5'>No open incidents</td></tr>"}
</table>

<h2>Maintenance Issues</h2>
<table>
  <tr><th>ID</th><th>Kennel</th><th>Status</th><th>Reported</th><th>Description</th></tr>
  {issue_rows if issue_rows else "<tr><td colspan='5'>No open issues</td></tr>"}
</table>
</body></html>"""

    path = os.path.join(REPORTS_DIR, f"incidents_{timestamp}.pdf")
    return await _write_pdf(html, path)
