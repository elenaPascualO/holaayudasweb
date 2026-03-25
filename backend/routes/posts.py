"""Admin routes for social media post management."""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Header, Query, Request
from pydantic import BaseModel

from backend.routes.admin import _validate_token
from backend.services.rate_limiter import admin_limiter, get_client_ip
from backend.services.posts_db import (
    delete_post_async,
    get_post_async,
    list_posts_async,
    update_post_status_async,
)

router = APIRouter(prefix="/api/admin/posts", tags=["admin-posts"])
logger = logging.getLogger(__name__)

# Generation state — shared across endpoints
_generate_state: dict = {"status": "idle"}
_generate_task: asyncio.Task | None = None


class UpdateStatusRequest(BaseModel):
    """Request body for updating post status."""

    status: str  # 'published' | 'discarded'


@router.get("")
async def list_all_posts(
    request: Request,
    authorization: str = Header(...),
    status: str | None = Query(default=None),
    post_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    """List generated posts with optional filters."""
    _validate_token(authorization)
    admin_limiter.check(get_client_ip(request))
    return await list_posts_async(status=status, post_type=post_type, limit=limit)


@router.get("/generate/status")
async def generation_status(
    request: Request,
    authorization: str = Header(...),
) -> dict:
    """Check the status of post generation."""
    _validate_token(authorization)
    admin_limiter.check(get_client_ip(request))
    return _generate_state


@router.get("/{post_id}")
async def get_single_post(
    post_id: int,
    request: Request,
    authorization: str = Header(...),
) -> dict:
    """Get a single post by ID."""
    _validate_token(authorization)
    admin_limiter.check(get_client_ip(request))
    post = await get_post_async(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.patch("/{post_id}")
async def update_status(
    post_id: int,
    body: UpdateStatusRequest,
    request: Request,
    authorization: str = Header(...),
) -> dict:
    """Update a post's status (publish or discard)."""
    _validate_token(authorization)
    admin_limiter.check(get_client_ip(request))

    if body.status not in ("published", "discarded"):
        raise HTTPException(
            status_code=400,
            detail="Status must be 'published' or 'discarded'",
        )

    updated = await update_post_status_async(post_id, body.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"id": post_id, "status": body.status}


@router.delete("/{post_id}")
async def remove_post(
    post_id: int,
    request: Request,
    authorization: str = Header(...),
) -> dict:
    """Delete a post."""
    _validate_token(authorization)
    admin_limiter.check(get_client_ip(request))
    deleted = await delete_post_async(post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"id": post_id, "deleted": True}


@router.post("/generate")
async def trigger_generation(
    request: Request,
    authorization: str = Header(...),
    post_type: str = Query(default="auto"),
) -> dict:
    """Trigger post generation in background."""
    global _generate_task
    _validate_token(authorization)
    admin_limiter.check(get_client_ip(request))

    if _generate_state.get("status") == "running":
        raise HTTPException(status_code=409, detail="Generation already running")

    valid_types = [
        "auto",
        "ayuda_destacada",
        "datos_semana",
        "cierre_inminente",
        "tematico",
        "top_organismo",
        "dato_curioso",
    ]
    if post_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid post_type. Valid: {valid_types}",
        )

    _generate_state.update({
        "status": "running",
        "post_type": post_type,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "result": None,
        "error": None,
    })

    _generate_task = asyncio.create_task(_run_generation_background(post_type))
    return {"status": "started", "post_type": post_type}


async def _run_generation_background(post_type: str) -> None:
    """Run post generation in background task."""
    try:
        from backend.scripts.generate_posts import run_generation

        result = await run_generation(post_type)
        _generate_state.update({
            "status": "completed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
        })
        logger.info("Post generation completed: %s", result)
    except asyncio.CancelledError:
        _generate_state["status"] = "cancelled"
        logger.info("Post generation cancelled")
    except Exception as e:
        _generate_state.update({
            "status": "failed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        })
        logger.error("Post generation failed: %s", e)


def cancel_generate_task() -> None:
    """Cancel any running generation task. Called during app shutdown."""
    global _generate_task
    if _generate_task and not _generate_task.done():
        _generate_task.cancel()
        logger.info("Cancelled running post generation task")
    _generate_task = None
