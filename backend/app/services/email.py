"""Email service using aiosmtplib. Credentials from smtp.json.

Sends:
  - PDF receipt (when auto_email_receipt=true or staff clicks Email)
  - Portal one-time link
  - 14-day billing cycle alert (to staff inbox)
"""

import logging
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from ..config import get_smtp

logger = logging.getLogger(__name__)


async def send_receipt(to_email: str, owner_name: str, pdf_path: str) -> bool:
    """Email PDF receipt as attachment. Returns True on success."""
    try:
        cfg = get_smtp()

        msg = MIMEMultipart()
        msg["From"] = cfg["username"]
        msg["To"] = to_email
        msg["Subject"] = "Your Kennel Stay Receipt"

        body = (
            f"Dear {owner_name},\n\n"
            "Please find your receipt attached for your dog's recent kennel stay.\n\n"
            "Thank you for choosing us!\n"
        )
        msg.attach(MIMEText(body, "plain"))

        # Attach PDF if the file exists
        if pdf_path and os.path.isfile(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_data = f.read()
            attachment = MIMEApplication(pdf_data, _subtype="pdf")
            attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=os.path.basename(pdf_path),
            )
            msg.attach(attachment)
        else:
            logger.warning("send_receipt: PDF not found at %s — sending without attachment", pdf_path)

        await aiosmtplib.send(
            msg,
            hostname=cfg["server"],
            port=cfg["port"],
            use_tls=cfg.get("use_tls", True),
            username=cfg["username"],
            password=cfg["password"],
        )
        return True

    except Exception as exc:
        logger.error("send_receipt failed: %s", exc)
        return False


async def send_portal_link(to_email: str, owner_name: str, link: str) -> bool:
    """Email the 7-day one-time portal link."""
    try:
        cfg = get_smtp()

        msg = MIMEMultipart()
        msg["From"] = cfg["username"]
        msg["To"] = to_email
        msg["Subject"] = "Your Kennel Portal Access Link"

        body = (
            f"Dear {owner_name},\n\n"
            "You can access your kennel portal using the link below. "
            "This link is valid for 7 days and can only be used once.\n\n"
            f"{link}\n\n"
            "If you did not request this link, please ignore this email.\n"
        )
        msg.attach(MIMEText(body, "plain"))

        await aiosmtplib.send(
            msg,
            hostname=cfg["server"],
            port=cfg["port"],
            use_tls=cfg.get("use_tls", True),
            username=cfg["username"],
            password=cfg["password"],
        )
        return True

    except Exception as exc:
        logger.error("send_portal_link failed: %s", exc)
        return False


async def send_billing_alert(
    staff_email: str, owner_name: str, reservation_id: str, amount_due: float
) -> bool:
    """Alert staff that a 14-day billing cycle has elapsed for an extended stay."""
    try:
        cfg = get_smtp()

        msg = MIMEMultipart()
        msg["From"] = cfg["username"]
        msg["To"] = staff_email
        msg["Subject"] = f"14-Day Billing Cycle Alert — Reservation {reservation_id}"

        body = (
            f"Staff Notice,\n\n"
            f"A 14-day billing cycle has elapsed for an extended stay.\n\n"
            f"Owner: {owner_name}\n"
            f"Reservation ID: {reservation_id}\n"
            f"Amount Due: ${amount_due:.2f}\n\n"
            "Please review and process the billing cycle in the management system.\n"
        )
        msg.attach(MIMEText(body, "plain"))

        await aiosmtplib.send(
            msg,
            hostname=cfg["server"],
            port=cfg["port"],
            use_tls=cfg.get("use_tls", True),
            username=cfg["username"],
            password=cfg["password"],
        )
        return True

    except Exception as exc:
        logger.error("send_billing_alert failed: %s", exc)
        return False
