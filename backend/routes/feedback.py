"""Feedback submission route."""

import json
import logging
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

try:
    from backend.config import SMTP_EMAIL, SMTP_APP_PASSWORD, FEEDBACK_EMAIL_TO
except ImportError:
    from config import SMTP_EMAIL, SMTP_APP_PASSWORD, FEEDBACK_EMAIL_TO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["feedback"])

FEEDBACK_FILE = Path(__file__).parent.parent / "feedback.jsonl"

# Simple in-memory rate limit: max 5 submissions per IP per hour
_rate_limit: dict[str, list[float]] = {}
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 3600  # seconds


class FeedbackRequest(BaseModel):
    """Feedback submission payload."""

    email: str = Field(default="", max_length=254)
    message: str = Field(min_length=1, max_length=2000)


def _check_rate_limit(client_ip: str) -> None:
    """Raise 429 if client has exceeded the submission limit."""
    now = time.time()
    timestamps = _rate_limit.get(client_ip, [])
    timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    if len(timestamps) >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many submissions. Try again later.")
    timestamps.append(now)
    _rate_limit[client_ip] = timestamps


def _send_feedback_email(email: str | None, message: str) -> None:
    """Send feedback notification via Gmail SMTP."""
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD or not FEEDBACK_EMAIL_TO:
        logger.warning("Email notification not configured, skipping")
        return

    reply_from = email or "anonimo"
    subject = f"[Hola Ayudas] Feedback de {reply_from}"
    body = f"Mensaje de feedback en Hola Ayudas:\n\nDe: {reply_from}\n\n{message}"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = FEEDBACK_EMAIL_TO
    if email:
        msg["Reply-To"] = email
    msg.set_content(body)

    try:
        smtp = smtplib.SMTP("smtp.gmail.com", 587)
        smtp.starttls()
        smtp.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        smtp.send_message(msg)
        smtp.quit()
    except Exception:
        logger.exception("Failed to send feedback email")


@router.post("/feedback", status_code=201)
async def submit_feedback(body: FeedbackRequest, request: Request) -> dict[str, str]:
    """Save a feedback message and send email notification."""
    _check_rate_limit(request.client.host if request.client else "unknown")

    email = body.email.strip() or None
    message = body.message.strip()

    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "email": email,
        "message": message,
    }

    with FEEDBACK_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    _send_feedback_email(email, message)

    return {"status": "ok"}