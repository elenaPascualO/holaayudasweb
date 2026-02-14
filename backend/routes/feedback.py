"""Feedback submission route."""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

try:
    from backend.config import DISCORD_WEBHOOK_URL
except ImportError:
    from config import DISCORD_WEBHOOK_URL

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


async def _send_discord_notification(email: str | None, message: str) -> None:
    """Send feedback notification to Discord via webhook."""
    if not DISCORD_WEBHOOK_URL:
        logger.warning("DISCORD_WEBHOOK_URL not configured, skipping notification")
        return

    sender = email or "anonymous"
    payload = {
        "embeds": [
            {
                "title": "New feedback",
                "color": 0x2563EB,
                "fields": [
                    {"name": "From", "value": sender, "inline": True},
                    {"name": "Message", "value": message},
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10.0)
            resp.raise_for_status()
    except Exception:
        logger.exception("Failed to send Discord notification")


@router.post("/feedback", status_code=201)
async def submit_feedback(body: FeedbackRequest, request: Request) -> dict[str, str]:
    """Save a feedback message and send Discord notification."""
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

    await _send_discord_notification(email, message)

    return {"status": "ok"}
