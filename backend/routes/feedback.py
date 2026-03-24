"""Feedback submission route."""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

try:
    from backend.config import DISCORD_WEBHOOK_URL
    from backend.services.rate_limiter import feedback_limiter, get_client_ip
except ImportError:
    from config import DISCORD_WEBHOOK_URL
    from services.rate_limiter import feedback_limiter, get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["feedback"])

FEEDBACK_FILE = Path(__file__).parent.parent / "feedback.jsonl"


class FeedbackRequest(BaseModel):
    """Feedback submission payload."""

    email: str = Field(default="", max_length=254)
    message: str = Field(min_length=1, max_length=2000)


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
    feedback_limiter.check(get_client_ip(request))

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
