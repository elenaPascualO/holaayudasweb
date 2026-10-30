"""Tests for admin sync endpoints — background task + status."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.routes import admin as admin_module


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def reset_sync_state():
    """Reset admin sync state before each test."""
    admin_module.admin_limiter._hits.clear()
    admin_module._sync_state = {"status": "idle"}
    admin_module._sync_task = None
    admin_module._last_result_by_mode.clear()
    yield
    # Cleanup: cancel any lingering task
    if admin_module._sync_task and not admin_module._sync_task.done():
        admin_module._sync_task.cancel()
    admin_module._sync_state = {"status": "idle"}
    admin_module._sync_task = None
    admin_module._last_result_by_mode.clear()


AUTH_HEADER = {"Authorization": "Bearer test-secret"}


@pytest.fixture(autouse=True)
def set_admin_secret():
    """Set ADMIN_SECRET for tests."""
    with patch.object(admin_module, "ADMIN_SECRET", "test-secret"):
        yield


async def test_sync_post_returns_started_immediately(client):
    """POST /sync/convocatorias returns 'started' without waiting for sync."""
    # Make run_sync hang forever (we'll cancel it)
    never_finishes = asyncio.Future()

    async def fake_run_sync(mode, progress_callback=None):
        await never_finishes
        return {}

    with patch(
        "backend.routes.admin.run_sync",
        side_effect=fake_run_sync,
        create=True,
    ):
        with patch(
            "backend.scripts.sync_convocatorias.run_sync",
            side_effect=fake_run_sync,
        ):
            response = await client.post(
                "/api/admin/sync/convocatorias?mode=full-list",
                headers=AUTH_HEADER,
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["mode"] == "full-list"


async def test_sync_rejects_if_already_running(client):
    """POST /sync/convocatorias returns 'skipped' when sync is already running."""
    # Set state to running
    admin_module._sync_state = {"status": "running", "mode": "full-list"}

    response = await client.post(
        "/api/admin/sync/convocatorias?mode=daily",
        headers=AUTH_HEADER,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "skipped"
    assert "already in progress" in data["reason"]


async def test_sync_status_returns_idle(client):
    """GET /sync/convocatorias/status returns idle by default."""
    response = await client.get(
        "/api/admin/sync/convocatorias/status",
        headers=AUTH_HEADER,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "idle"


async def test_sync_status_returns_running_with_progress(client):
    """GET status returns running state with progress info."""
    admin_module._sync_state = {
        "status": "running",
        "mode": "full-list",
        "started_at": "2026-01-01T00:00:00+00:00",
        "progress": {
            "phase": "full-list",
            "total_pages": 12000,
            "pages_processed": 500,
            "records_inserted": 25000,
        },
    }

    response = await client.get(
        "/api/admin/sync/convocatorias/status",
        headers=AUTH_HEADER,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["progress"]["pages_processed"] == 500
    assert data["progress"]["total_pages"] == 12000


async def test_sync_status_returns_completed(client):
    """GET status returns completed state with result."""
    admin_module._sync_state = {
        "status": "completed",
        "mode": "daily",
        "result": {"mode": "daily", "new_convocatorias": 42},
        "finished_at": "2026-01-01T01:00:00+00:00",
    }

    response = await client.get(
        "/api/admin/sync/convocatorias/status",
        headers=AUTH_HEADER,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["new_convocatorias"] == 42


async def test_sync_status_requires_auth(client):
    """GET status without auth returns 422 (missing header) or 401."""
    response = await client.get("/api/admin/sync/convocatorias/status")
    assert response.status_code == 422


async def test_sync_post_requires_auth(client):
    """POST sync without auth returns 422 (missing header) or 401."""
    response = await client.post("/api/admin/sync/convocatorias")
    assert response.status_code == 422


async def test_sync_post_invalid_mode(client):
    """POST with invalid mode returns 400."""
    response = await client.post(
        "/api/admin/sync/convocatorias?mode=invalid",
        headers=AUTH_HEADER,
    )

    assert response.status_code == 400


async def test_background_sync_updates_state_on_completion(client):
    """Background task updates state to completed when sync finishes."""
    async def fake_run_sync(mode, progress_callback=None):
        if progress_callback:
            progress_callback({"phase": "full-list", "total_pages": 1, "pages_processed": 1})
        return {"mode": mode, "total_inserted": 10}

    with patch(
        "backend.scripts.sync_convocatorias.run_sync",
        side_effect=fake_run_sync,
    ):
        response = await client.post(
            "/api/admin/sync/convocatorias?mode=full-list",
            headers=AUTH_HEADER,
        )
        assert response.json()["status"] == "started"

        # Give the background task time to complete
        await asyncio.sleep(0.1)

    assert admin_module._sync_state["status"] == "completed"
    assert admin_module._sync_state["result"]["total_inserted"] == 10


async def test_background_sync_updates_state_on_failure(client):
    """Background task updates state to failed when sync raises."""
    async def fake_run_sync(mode, progress_callback=None):
        raise RuntimeError("BDNS API is down")

    with patch(
        "backend.scripts.sync_convocatorias.run_sync",
        side_effect=fake_run_sync,
    ):
        response = await client.post(
            "/api/admin/sync/convocatorias?mode=daily",
            headers=AUTH_HEADER,
        )
        assert response.json()["status"] == "started"

        # Give the background task time to fail
        await asyncio.sleep(0.1)

    assert admin_module._sync_state["status"] == "failed"
    assert "BDNS API is down" in admin_module._sync_state["error"]


async def test_embeddings_skipped_when_last_detail_failed(client):
    """Embeddings backfill is skipped if last detail backfill failed."""
    admin_module._last_result_by_mode["backfill-detail"] = {
        "status": "failed",
        "mode": "backfill-detail",
        "error": "BDNS API timeout",
        "finished_at": "2026-03-11T08:00:00+00:00",
    }

    response = await client.post(
        "/api/admin/sync/convocatorias?mode=backfill-embeddings",
        headers=AUTH_HEADER,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "skipped"
    assert "detail failed" in data["reason"].lower()
    assert data["detail_error"] == "BDNS API timeout"


async def test_embeddings_allowed_when_last_detail_succeeded(client):
    """Embeddings backfill runs normally if last detail backfill succeeded."""
    admin_module._last_result_by_mode["backfill-detail"] = {
        "status": "completed",
        "mode": "backfill-detail",
        "finished_at": "2026-03-11T08:00:00+00:00",
    }

    async def fake_run_sync(mode, progress_callback=None):
        return {"mode": mode, "embeddings_generated": 5}

    with patch(
        "backend.scripts.sync_convocatorias.run_sync",
        side_effect=fake_run_sync,
    ):
        response = await client.post(
            "/api/admin/sync/convocatorias?mode=backfill-embeddings",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200
    assert response.json()["status"] == "started"


async def test_embeddings_allowed_when_no_detail_history(client):
    """Embeddings backfill runs if there's no detail history (e.g. after restart)."""
    async def fake_run_sync(mode, progress_callback=None):
        return {"mode": mode, "embeddings_generated": 5}

    with patch(
        "backend.scripts.sync_convocatorias.run_sync",
        side_effect=fake_run_sync,
    ):
        response = await client.post(
            "/api/admin/sync/convocatorias?mode=backfill-embeddings",
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200
    assert response.json()["status"] == "started"


async def test_failed_detail_tracked_in_history(client):
    """Failed detail sync is recorded in _last_result_by_mode."""
    async def fake_run_sync(mode, progress_callback=None):
        raise RuntimeError("Connection reset")

    with patch(
        "backend.scripts.sync_convocatorias.run_sync",
        side_effect=fake_run_sync,
    ):
        await client.post(
            "/api/admin/sync/convocatorias?mode=backfill-detail",
            headers=AUTH_HEADER,
        )
        await asyncio.sleep(0.1)

    assert admin_module._last_result_by_mode["backfill-detail"]["status"] == "failed"
    assert "Connection reset" in admin_module._last_result_by_mode["backfill-detail"]["error"]


async def test_faiss_rebuild_requires_token(client):
    """POST /faiss/rebuild rejects requests without a valid token."""
    response = await client.post(
        "/api/admin/faiss/rebuild", headers={"Authorization": "Bearer wrong"}
    )
    assert response.status_code == 401


async def test_faiss_rebuild_starts_in_background(client):
    """POST /faiss/rebuild launches the rebuild and returns immediately."""
    with patch("backend.services.faiss_index.load_index_from_db") as mock_rebuild:
        response = await client.post("/api/admin/faiss/rebuild", headers=AUTH_HEADER)
        await asyncio.sleep(0.1)

    assert response.status_code == 200
    assert response.json()["status"] == "started"
    mock_rebuild.assert_called_once()


async def test_faiss_rebuild_skipped_while_building(client):
    """A rebuild is refused while another build/update holds the write lock."""
    from backend.services import faiss_index

    with patch("backend.services.faiss_index.load_index_from_db") as mock_rebuild:
        with faiss_index._write_lock:
            response = await client.post("/api/admin/faiss/rebuild", headers=AUTH_HEADER)

    assert response.json()["status"] == "skipped"
    mock_rebuild.assert_not_called()


@pytest.fixture
def mock_generate_sitemaps():
    """Replace sitemap generation so tests never write sitemap files."""
    from unittest.mock import MagicMock

    mock = MagicMock(return_value={"status": "completed", "files": 1, "urls": 1})
    with patch("backend.services.sitemaps.generate_all", mock):
        yield mock


async def test_sitemaps_regenerate_requires_token(client, mock_generate_sitemaps):
    response = await client.post(
        "/api/admin/sitemaps/regenerate", headers={"Authorization": "Bearer wrong"}
    )
    assert response.status_code == 401
    mock_generate_sitemaps.assert_not_called()


async def test_sitemaps_regenerate_starts_in_background(client, mock_generate_sitemaps):
    response = await client.post("/api/admin/sitemaps/regenerate", headers=AUTH_HEADER)
    await asyncio.sleep(0.1)

    assert response.status_code == 200
    assert response.json()["status"] == "started"
    mock_generate_sitemaps.assert_called_once()


async def test_sitemaps_regenerate_skipped_while_generating(client, mock_generate_sitemaps):
    from backend.services import sitemaps

    with sitemaps._gen_lock:
        response = await client.post("/api/admin/sitemaps/regenerate", headers=AUTH_HEADER)

    assert response.json()["status"] == "skipped"
    mock_generate_sitemaps.assert_not_called()


async def test_sitemaps_status_endpoint(client, mock_generate_sitemaps):
    response = await client.get("/api/admin/sitemaps/status", headers=AUTH_HEADER)
    assert response.status_code == 200
    assert "generating" in response.json()
    assert "generated_at" in response.json()


@pytest.mark.parametrize("mode,expected_calls", [
    ("daily", 1),
    ("backfill-detail", 0),
    ("backfill-embeddings", 0),
])
async def test_daily_sync_triggers_sitemap_regeneration(
    client, mock_generate_sitemaps, mode, expected_calls
):
    async def fake_run_sync(mode, progress_callback=None):
        return {"mode": mode}

    with patch("backend.scripts.sync_convocatorias.run_sync", side_effect=fake_run_sync):
        await client.post(f"/api/admin/sync/convocatorias?mode={mode}", headers=AUTH_HEADER)
        await asyncio.sleep(0.2)

    assert admin_module._sync_state["status"] == "completed"
    assert mock_generate_sitemaps.call_count == expected_calls
