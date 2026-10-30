"""Admin routes — protected operations triggered by cron or manual calls."""

import asyncio
import hmac
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Header, Query, Request

from backend.config import ADMIN_SECRET
from backend.services.rate_limiter import admin_limiter, get_client_ip

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

# FAISS rebuild task (kept referenced so it isn't garbage-collected)
_faiss_rebuild_task: asyncio.Task | None = None

# Sitemap generation task (kept referenced so it isn't garbage-collected)
_sitemap_task: asyncio.Task | None = None


def _validate_token(authorization: str) -> None:
    """Validate admin bearer token."""
    if not ADMIN_SECRET:
        logger.error("ADMIN_SECRET is not set — rejecting admin request")
        raise HTTPException(status_code=401, detail="Unauthorized")
    expected = f"Bearer {ADMIN_SECRET}"
    if not hmac.compare_digest(authorization, expected):
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

        # Invalidate caches so next request sees fresh data
        from backend.routes.seo import invalidate_sitemap_cache
        from backend.services.convocatorias_db import invalidate_has_data_cache

        invalidate_sitemap_cache()
        invalidate_has_data_cache()

        # Regenerate pregenerated sitemaps with the new data (own background task)
        if mode == "daily":
            _start_sitemap_generation()

        # Add newly embedded vectors to FAISS (incremental, no rebuild)
        if mode in ("daily", "backfill-embeddings") and not os.environ.get("TESTING"):
            try:
                import backend.services.faiss_index as faiss_index

                logger.info("Updating FAISS index after %s sync", mode)
                await asyncio.to_thread(faiss_index.sync_from_db)
            except Exception as e:
                logger.error("Failed to update FAISS index: %s", e)
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

        from backend.services.email_notify import send_sync_failure_email

        await send_sync_failure_email("convocatorias", str(e), mode=mode)


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

        from backend.services.email_notify import send_sync_failure_email

        await send_sync_failure_email("beneficiarios", str(e))


@router.post("/sync/beneficiarios")
async def trigger_sync(
    request: Request,
    authorization: str = Header(..., description="Bearer token matching ADMIN_SECRET"),
) -> dict:
    """Trigger beneficiarios sync in background and return immediately.

    Protected by a Bearer token. Intended to be called from a scheduled task (cron).
    Use GET /api/admin/sync/beneficiarios/status to check progress.
    """
    global _beneficiarios_sync_state, _beneficiarios_sync_task

    admin_limiter.check(get_client_ip(request))
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
    request: Request,
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

    admin_limiter.check(get_client_ip(request))
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


@router.get("/faiss/status")
async def get_faiss_status(
    authorization: str = Header(..., description="Bearer token matching ADMIN_SECRET"),
) -> dict:
    """Return FAISS vector index status (ready, total vectors, index type, building, on disk)."""
    _validate_token(authorization)

    import backend.services.faiss_index as faiss_index

    return faiss_index.get_stats()


async def _run_faiss_rebuild_background() -> None:
    """Retrain the FAISS index from SQLite in a worker thread."""
    import backend.services.faiss_index as faiss_index

    logger.info("FAISS rebuild starting")
    try:
        await asyncio.to_thread(faiss_index.load_index_from_db)
        logger.info("FAISS rebuild completed")
    except Exception as e:
        logger.exception("FAISS rebuild failed")

        from backend.services.email_notify import send_sync_failure_email

        await send_sync_failure_email("faiss-rebuild", str(e))


@router.post("/faiss/rebuild")
async def trigger_faiss_rebuild(
    request: Request,
    authorization: str = Header(..., description="Bearer token matching ADMIN_SECRET"),
) -> dict:
    """Retrain the FAISS index from scratch in background and save it to disk.

    Only needed occasionally (e.g. every few months) to refresh the trained
    centroids; daily syncs add vectors incrementally. Takes several minutes and
    several GB of RAM. The current index keeps serving searches meanwhile.

    Use GET /api/admin/faiss/status to check progress (building / built_at).
    """
    global _faiss_rebuild_task

    admin_limiter.check(get_client_ip(request))
    _validate_token(authorization)

    import backend.services.faiss_index as faiss_index

    if faiss_index.is_building():
        return {"status": "skipped", "reason": "FAISS index build or update already in progress"}

    _faiss_rebuild_task = asyncio.create_task(_run_faiss_rebuild_background())
    return {"status": "started"}


async def _run_sitemap_generation_background() -> None:
    """Regenerate all sitemap files in a worker thread."""
    from backend.services import sitemaps

    try:
        result = await asyncio.to_thread(sitemaps.generate_all)
        logger.info("Sitemap generation finished: %s", result)
    except Exception as e:
        logger.exception("Sitemap generation failed")

        from backend.services.email_notify import send_sync_failure_email

        await send_sync_failure_email("sitemaps", str(e))


def _start_sitemap_generation() -> None:
    """Launch sitemap regeneration as a background task."""
    global _sitemap_task
    _sitemap_task = asyncio.create_task(_run_sitemap_generation_background())


@router.post("/sitemaps/regenerate")
async def trigger_sitemaps_regeneration(
    request: Request,
    authorization: str = Header(..., description="Bearer token matching ADMIN_SECRET"),
) -> dict:
    """Regenerate all sitemap files in background.

    Normally not needed: sitemaps regenerate after each daily sync and at
    startup when older than 24h. Previous files keep being served meanwhile.

    Use GET /api/admin/sitemaps/status to check progress.
    """
    admin_limiter.check(get_client_ip(request))
    _validate_token(authorization)

    from backend.services import sitemaps

    if sitemaps.is_generating():
        return {"status": "skipped", "reason": "Sitemap generation already in progress"}

    _start_sitemap_generation()
    return {"status": "started"}


@router.get("/sitemaps/status")
async def get_sitemaps_status(
    authorization: str = Header(..., description="Bearer token matching ADMIN_SECRET"),
) -> dict:
    """Return sitemap generation status (generating, generated_at, files, urls)."""
    _validate_token(authorization)

    from backend.services import sitemaps

    return await asyncio.to_thread(sitemaps.get_status)
