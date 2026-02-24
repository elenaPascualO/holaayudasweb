"""Admin routes — protected operations triggered by cron or manual calls."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Header

from backend.config import ADMIN_SECRET

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)

# Track whether a sync is already running to prevent overlapping syncs
_sync_running = False


@router.post("/sync")
async def trigger_sync(
    authorization: str = Header(..., description="Bearer token matching ADMIN_SECRET"),
) -> dict:
    """Trigger beneficiarios sync from BDNS API into local SQLite.

    Protected by a Bearer token. Intended to be called from a Railway cron job:
        curl -X POST https://holaayudas.com/api/admin/sync -H "Authorization: Bearer <token>"
    """
    global _sync_running

    # Validate token
    expected = f"Bearer {ADMIN_SECRET}"
    if not ADMIN_SECRET or authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if _sync_running:
        return {"status": "skipped", "reason": "Sync already in progress"}

    _sync_running = True
    try:
        from backend.scripts.sync_beneficiarios import run_sync

        await run_sync()
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Sync failed")
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")
    finally:
        _sync_running = False
