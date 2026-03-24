"""Tests for security hardening: rate limiter, headers, input validation, error handling."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.services.rate_limiter import RateLimiter, get_client_ip


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# RateLimiter unit tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    """Unit tests for the RateLimiter class."""

    def test_allows_requests_under_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.check("ip1")  # should not raise

    def test_blocks_requests_over_limit(self):
        from fastapi import HTTPException

        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.check("ip1")
        limiter.check("ip1")
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("ip1")
        assert exc_info.value.status_code == 429

    def test_different_keys_independent(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.check("ip1")
        limiter.check("ip2")  # should not raise

    def test_window_expires(self):
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        limiter.check("ip1")

        # Manually expire the timestamp
        limiter._hits["ip1"] = [time.time() - 2]
        limiter.check("ip1")  # should not raise after window expires

    def test_cleans_old_timestamps(self):
        limiter = RateLimiter(max_requests=2, window_seconds=10)
        limiter._hits["ip1"] = [time.time() - 20, time.time() - 15]
        limiter.check("ip1")  # old timestamps should be cleaned
        assert len(limiter._hits["ip1"]) == 1


# ---------------------------------------------------------------------------
# get_client_ip tests
# ---------------------------------------------------------------------------


class TestGetClientIp:
    """Tests for X-Forwarded-For IP extraction."""

    def test_uses_x_forwarded_for_first_ip(self):
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4, 10.0.0.1, 172.16.0.1"}
        request.client.host = "127.0.0.1"
        assert get_client_ip(request) == "1.2.3.4"

    def test_uses_x_forwarded_for_single_ip(self):
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "8.8.8.8"}
        request.client.host = "127.0.0.1"
        assert get_client_ip(request) == "8.8.8.8"

    def test_falls_back_to_client_host(self):
        request = MagicMock()
        request.headers = {}
        request.client.host = "192.168.1.100"
        assert get_client_ip(request) == "192.168.1.100"

    def test_returns_unknown_when_no_client(self):
        request = MagicMock()
        request.headers = {}
        request.client = None
        assert get_client_ip(request) == "unknown"


# ---------------------------------------------------------------------------
# Query max_length validation (422 for queries > 500 chars)
# ---------------------------------------------------------------------------


@patch("backend.routes.convocatorias.has_convocatorias_data", return_value=False)
async def test_search_rejects_query_over_500_chars(mock_has_data, client):
    """GET /api/convocatorias with q > 500 chars returns 422."""
    long_query = "a" * 501
    response = await client.get(f"/api/convocatorias?q={long_query}")
    assert response.status_code == 422


@patch("backend.routes.convocatorias.has_convocatorias_data", return_value=False)
async def test_search_accepts_query_at_500_chars(mock_has_data, client):
    """GET /api/convocatorias with q = 500 chars is accepted."""
    mock_search = AsyncMock(return_value={
        "content": [], "totalElements": 0, "totalPages": 0, "number": 0, "size": 20,
    })
    with patch("backend.routes.convocatorias.search_convocatorias", mock_search):
        response = await client.get(f"/api/convocatorias?q={'a' * 500}")
    assert response.status_code == 200


async def test_semantic_search_rejects_query_over_500_chars(client):
    """GET /api/search with q > 500 chars returns 422."""
    long_query = "b" * 501
    response = await client.get(f"/api/search?q={long_query}")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# CSV parameter validation (400 for non-numeric IDs)
# ---------------------------------------------------------------------------


@patch("backend.routes.convocatorias.has_convocatorias_data", return_value=True)
async def test_invalid_region_id_returns_400(mock_has_data, client):
    """GET /api/convocatorias with non-numeric region ID returns 400."""
    response = await client.get("/api/convocatorias?regiones=abc")
    assert response.status_code == 400
    assert "Invalid region ID" in response.json()["detail"]


@patch("backend.routes.convocatorias.has_convocatorias_data", return_value=True)
async def test_invalid_instrument_id_returns_400(mock_has_data, client):
    """GET /api/convocatorias with non-numeric instrument ID returns 400."""
    response = await client.get("/api/convocatorias?instrumentos=xyz")
    assert response.status_code == 400
    assert "Invalid instrument ID" in response.json()["detail"]


@patch("backend.routes.convocatorias.has_convocatorias_data", return_value=True)
async def test_invalid_beneficiary_type_id_returns_400(mock_has_data, client):
    """GET /api/convocatorias with non-numeric beneficiary type ID returns 400."""
    response = await client.get("/api/convocatorias?tiposBeneficiario=foo")
    assert response.status_code == 400
    assert "Invalid beneficiary type ID" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Admin token validation (hmac.compare_digest)
# ---------------------------------------------------------------------------


async def test_admin_wrong_token_returns_401(client):
    """Admin endpoints reject invalid tokens with 401."""
    response = await client.get(
        "/api/admin/sync/convocatorias/status",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401


async def test_admin_correct_token_accepted(client):
    """Admin endpoints accept correct token."""
    from backend.routes import admin as admin_module

    with patch.object(admin_module, "ADMIN_SECRET", "correct-secret"):
        response = await client.get(
            "/api/admin/sync/convocatorias/status",
            headers={"Authorization": "Bearer correct-secret"},
        )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------


async def test_security_headers_present(client):
    """All security headers are present in responses."""
    response = await client.get("/api/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers.get("Permissions-Policy", "")


async def test_hsts_only_in_production(client):
    """HSTS header is only set when IS_PRODUCTION is True."""
    response = await client.get("/api/health")
    # In test environment IS_PRODUCTION is False, so no HSTS
    assert "Strict-Transport-Security" not in response.headers


# ---------------------------------------------------------------------------
# Generic exception handler
# ---------------------------------------------------------------------------


async def test_unhandled_exception_returns_500_in_production(client):
    """Unhandled exceptions return generic 500 in production (no stack trace)."""
    # Patch IS_PRODUCTION at the module level where the middleware reads it
    import backend.main as main_module

    original = main_module.IS_PRODUCTION
    main_module.IS_PRODUCTION = True
    try:
        with patch(
            "backend.routes.convocatorias.has_convocatorias_data",
            side_effect=RuntimeError("secret internal error details"),
        ):
            response = await client.get("/api/convocatorias")
    finally:
        main_module.IS_PRODUCTION = original

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal server error"
    assert "secret internal error" not in str(body)
