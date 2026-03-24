"""Admin routes — protected operations triggered by cron or manual calls."""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Header, Query

from backend.config import ADMIN_SECRET

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)

# Beneficiarios sync state — shared across endpoints
_beneficiarios_sync_state: dict = {"status": "idle"}
_beneficiarios_sync_task: asyncio.Task | None = None

# Convocatorias sync state — shared across endpoints
_sync_state: dict = {"status": "idle"}
_sync_task: asyncio.Task | None = None

# Last completed/failed result per mode (in-memory, resets on restart)
_last_result_by_mode: dict[str, dict] = {}


def _validate_token(authorization: str) -> None:
    """Validate admin bearer token."""
    if not ADMIN_SECRET:
        logger.error("ADMIN_SECRET is not set — rejecting admin request")
        raise HTTPException(status_code=401, detail="Unauthorized")
    expected = f"Bearer {ADMIN_SECRET}"
    if authorization != expected:
        logger.warning("Invalid admin token received (length=%d)", len(authorization))
        raise HTTPException(status_code=401, detail="Unauthorized")


def _update_sync_progress(progress: dict) -> None:
    """Callback invoked by sync script to report progress."""
    _sync_state["progress"] = progress


async def _run_sync_background(mode: str) -> None:
    """Run sync in background, updating _sync_state on completion or failure."""
    global _sync_state
    logger.info("Background sync starting: mode=%s", mode)
    try:
        from backend.scripts.sync_convocatorias import run_sync

        result = await run_sync(mode=mode, progress_callback=_update_sync_progress)
        finished = {
            "status": "completed",
            "mode": mode,
            "result": result,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        _sync_state = finished
        _last_result_by_mode[mode] = finished
        logger.info("Background sync completed: mode=%s result=%s", mode, result)

        # Invalidate sitemap caches so next crawl sees fresh data
        from backend.routes.seo import invalidate_sitemap_cache

        invalidate_sitemap_cache()
    except asyncio.CancelledError:
        finished = {
            "status": "cancelled",
            "mode": mode,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        _sync_state = finished
        _last_result_by_mode[mode] = finished
    except Exception as e:
        logger.exception("Background convocatorias sync failed")
        finished = {
            "status": "failed",
            "mode": mode,
            "error": str(e),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        _sync_state = finished
        _last_result_by_mode[mode] = finished


def cancel_sync_task() -> None:
    """Cancel running sync tasks if any. Called during app shutdown."""
    global _sync_task, _beneficiarios_sync_task
    if _sync_task and not _sync_task.done():
        _sync_task.cancel()
        logger.info("Cancelled running convocatorias sync task on shutdown")
    if _beneficiarios_sync_task and not _beneficiarios_sync_task.done():
        _beneficiarios_sync_task.cancel()
        logger.info("Cancelled running beneficiarios sync task on shutdown")


async def _run_beneficiarios_sync_background() -> None:
    """Run beneficiarios sync in background, updating state on completion or failure."""
    global _beneficiarios_sync_state
    logger.info("Background beneficiarios sync starting")
    try:
        from backend.scripts.sync_beneficiarios import run_sync

        result = await run_sync()
        _beneficiarios_sync_state = {
            "status": "completed",
            "result": result,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Background beneficiarios sync completed: %s", result)
    except asyncio.CancelledError:
        _beneficiarios_sync_state = {
            "status": "cancelled",
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("Background beneficiarios sync failed")
        _beneficiarios_sync_state = {
            "status": "failed",
            "error": str(e),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }


@router.post("/sync/beneficiarios")
async def trigger_sync(
    authorization: str = Header(..., description="Bearer token matching ADMIN_SECRET"),
) -> dict:
    """Trigger beneficiarios sync in background and return immediately.

    Protected by a Bearer token. Intended to be called from a Railway cron job.
    Use GET /api/admin/sync/beneficiarios/status to check progress.
    """
    global _beneficiarios_sync_state, _beneficiarios_sync_task

    logger.info("Received beneficiarios sync request")
    _validate_token(authorization)

    if _beneficiarios_sync_state.get("status") == "running":
        logger.info("Beneficiarios sync already running, skipping")
        return {"status": "skipped", "reason": "Sync already in progress"}

    _beneficiarios_sync_state = {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    _beneficiarios_sync_task = asyncio.create_task(_run_beneficiarios_sync_background())
    logger.info("Background beneficiarios sync task created")

    return {"status": "started"}


@router.get("/sync/beneficiarios/status")
async def get_beneficiarios_sync_status(
    authorization: str = Header(..., description="Bearer token matching ADMIN_SECRET"),
) -> dict:
    """Return current state of the beneficiarios sync task."""
    _validate_token(authorization)
    return _beneficiarios_sync_state


@router.get("/sync/beneficiarios/stats")
async def get_beneficiarios_stats(
    authorization: str = Header(..., description="Bearer token matching ADMIN_SECRET"),
) -> dict:
    """Return beneficiarios DB stats: totals, per-year breakdown, and sync delta."""
    _validate_token(authorization)

    from backend.services.beneficiarios_db import get_beneficiarios_stats

    return await asyncio.to_thread(get_beneficiarios_stats)


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
        backfill-detail - Fetch detail for 30000 records without it
        backfill-embeddings - Generate embeddings for 10000 records (skipped if last detail failed)

    Use GET /api/admin/sync/convocatorias/status to check progress.
    """
    global _sync_state, _sync_task

    logger.info("Received convocatorias sync request: mode=%s", mode)
    _validate_token(authorization)

    valid_modes = {"daily", "full-list", "backfill-detail", "backfill-embeddings"}
    if mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Must be one of: {', '.join(valid_modes)}",
        )

    if _sync_state.get("status") == "running":
        logger.info("Sync already running, skipping")
        return {"status": "skipped", "reason": "Convocatorias sync already in progress"}

    # Embeddings depend on detail — skip if last detail run failed
    if mode == "backfill-embeddings":
        last_detail = _last_result_by_mode.get("backfill-detail")
        if last_detail and last_detail["status"] == "failed":
            logger.warning(
                "Skipping backfill-embeddings: last backfill-detail failed at %s: %s",
                last_detail.get("finished_at"),
                last_detail.get("error"),
            )
            return {
                "status": "skipped",
                "reason": "Last backfill-detail failed, fix before running embeddings",
                "detail_error": last_detail.get("error"),
                "detail_finished_at": last_detail.get("finished_at"),
            }

    _sync_state = {
        "status": "running",
        "mode": mode,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "progress": {},
    }
    _sync_task = asyncio.create_task(_run_sync_background(mode))
    logger.info("Background sync task created: mode=%s", mode)

    return {"status": "started", "mode": mode}


@router.get("/sync/convocatorias/status")
async def get_convocatorias_sync_status(
    authorization: str = Header(..., description="Bearer token matching ADMIN_SECRET"),
) -> dict:
    """Return current state of the convocatorias sync task."""
    _validate_token(authorization)
    logger.info("Sync status queried: %s", _sync_state.get("status"))
    return _sync_state


@router.get("/sync/convocatorias/stats")
async def get_convocatorias_backfill_stats(
    authorization: str = Header(..., description="Bearer token matching ADMIN_SECRET"),
) -> dict:
    """Return backfill progress counters for detail and embeddings."""
    _validate_token(authorization)

    from backend.services.convocatorias_db import get_backfill_stats

    return await asyncio.to_thread(get_backfill_stats)
