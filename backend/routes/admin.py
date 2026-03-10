"""Admin routes — protected operations triggered by cron or manual calls."""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Header, Query

from backend.config import ADMIN_SECRET

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)

# Track whether beneficiarios sync is running
_beneficiarios_sync_running = False

# Convocatorias sync state — shared across endpoints
_sync_state: dict = {"status": "idle"}
_sync_task: asyncio.Task | None = None


def _validate_token(authorization: str) -> None:
    """Validate admin bearer token."""
    expected = f"Bearer {ADMIN_SECRET}"
    if not ADMIN_SECRET or authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _update_sync_progress(progress: dict) -> None:
    """Callback invoked by sync script to report progress."""
    _sync_state["progress"] = progress


async def _run_sync_background(mode: str) -> None:
    """Run sync in background, updating _sync_state on completion or failure."""
    global _sync_state
    try:
        from backend.scripts.sync_convocatorias import run_sync

        result = await run_sync(mode=mode, progress_callback=_update_sync_progress)
        _sync_state = {
            "status": "completed",
            "mode": mode,
            "result": result,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    except asyncio.CancelledError:
        _sync_state = {
            "status": "cancelled",
            "mode": mode,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("Background convocatorias sync failed")
        _sync_state = {
            "status": "failed",
            "mode": mode,
            "error": str(e),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }


def cancel_sync_task() -> None:
    """Cancel the running sync task if any. Called during app shutdown."""
    global _sync_task
    if _sync_task and not _sync_task.done():
        _sync_task.cancel()
        logger.info("Cancelled running sync task on shutdown")


@router.post("/sync")
async def trigger_sync(
    authorization: str = Header(..., description="Bearer token matching ADMIN_SECRET"),
) -> dict:
    """Trigger beneficiarios sync from BDNS API into local SQLite.

    Protected by a Bearer token. Intended to be called from a Railway cron job:
        curl -X POST https://holaayudas.com/api/admin/sync -H "Authorization: Bearer <token>"
    """
    global _beneficiarios_sync_running

    _validate_token(authorization)

    if _beneficiarios_sync_running:
        return {"status": "skipped", "reason": "Sync already in progress"}

    _beneficiarios_sync_running = True
    try:
        from backend.scripts.sync_beneficiarios import run_sync

        await run_sync()
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Beneficiarios sync failed")
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")
    finally:
        _beneficiarios_sync_running = False


@router.post("/sync/convocatorias")
async def trigger_convocatorias_sync(
    authorization: str = Header(..., description="Bearer token matching ADMIN_SECRET"),
    mode: str = Query(
        default="daily",
        description="Sync mode: daily, full-list, backfill-detail, backfill-embeddings",
    ),
) -> dict:
    """Trigger convocatorias sync in background and return immediately.

    Modes:
        daily - Incremental sync (new list + detail + embeddings)
        full-list - Full historical load (~610K records)
        backfill-detail - Fetch detail for 3000 records without it
        backfill-embeddings - Generate embeddings for 500 records

    Use GET /api/admin/sync/convocatorias/status to check progress.
    """
    global _sync_state, _sync_task

    _validate_token(authorization)

    valid_modes = {"daily", "full-list", "backfill-detail", "backfill-embeddings"}
    if mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Must be one of: {', '.join(valid_modes)}",
        )

    if _sync_state.get("status") == "running":
        return {"status": "skipped", "reason": "Convocatorias sync already in progress"}

    _sync_state = {
        "status": "running",
        "mode": mode,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "progress": {},
    }
    _sync_task = asyncio.create_task(_run_sync_background(mode))

    return {"status": "started", "mode": mode}


@router.get("/sync/convocatorias/status")
async def get_convocatorias_sync_status(
    authorization: str = Header(..., description="Bearer token matching ADMIN_SECRET"),
) -> dict:
    """Return current state of the convocatorias sync task."""
    _validate_token(authorization)
    return _sync_state
