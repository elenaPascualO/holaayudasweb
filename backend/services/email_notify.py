"""Email notifications for sync job failures."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from backend.config import (
    ALERT_EMAIL_TO,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)

logger = logging.getLogger(__name__)


def _is_configured() -> bool:
    """Check if SMTP settings are configured."""
    return all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, ALERT_EMAIL_TO])


def _send_email(subject: str, body: str) -> None:
    """Send an email synchronously. Intended to be called via asyncio.to_thread."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = ALERT_EMAIL_TO
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)

    logger.info("Alert email sent: %s", subject)


async def send_sync_failure_email(sync_type: str, error: str, mode: str | None = None) -> None:
    """Send email notification when a sync job fails.

    Args:
        sync_type: "convocatorias" or "beneficiarios".
        error: Error message from the exception.
        mode: Sync mode (only for convocatorias).
    """
    if not _is_configured():
        logger.debug("SMTP not configured, skipping failure email")
        return

    mode_info = f" (mode: {mode})" if mode else ""
    subject = f"[Hola Ayudas] Sync FAILED: {sync_type}{mode_info}"
    body = (
        f"The {sync_type} sync job has failed{mode_info}.\n\n"
        f"Error:\n{error}\n\n"
        f"Check the server logs for more details."
    )

    try:
        await asyncio.to_thread(_send_email, subject, body)
    except Exception:
        logger.exception("Failed to send sync failure email")
