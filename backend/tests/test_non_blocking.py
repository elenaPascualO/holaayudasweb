"""Routes must not run slow synchronous work (SQLite, FAISS) on the event loop.

Each test replaces a synchronous function with one that sleeps 0.6s, fires the
route, and 0.1s later fires /api/health. Timing is measured from the common
start: if the route blocks the loop, /api/health can't even wake up from its
sleep until the 0.6s call finishes (~0.6s). If it doesn't block, ~0.1s.
"""

import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.services.cache import cache
from backend.services.rate_limiter import search_limiter

SLOW_SECONDS = 0.6
MAX_HEALTH_SECONDS = 0.4


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def clean_state():
    """Empty the response cache (so routes hit the slow function) and rate limits."""
    cache.clear()
    search_limiter._hits.clear()
    yield
    cache.clear()


def _slow(return_value):
    def slow(*args, **kwargs):
        time.sleep(SLOW_SECONDS)
        return return_value
    return slow


async def _assert_health_not_blocked(client, slow_call) -> None:
    """Run slow_call concurrently with /api/health and check health isn't delayed."""
    start = time.monotonic()

    async def health_after_delay():
        await asyncio.sleep(0.1)
        response = await client.get("/api/health")
        return response, time.monotonic() - start

    _, (health_resp, health_done_at) = await asyncio.gather(slow_call, health_after_delay())

    assert health_resp.status_code == 200
    assert health_done_at < MAX_HEALTH_SECONDS, (
        f"/api/health finished at {health_done_at:.2f}s — blocked behind the slow call"
    )


@pytest.mark.parametrize("path,func,return_value", [
    ("/api/analytics/summary", "analytics_summary", {}),
    ("/api/analytics/by-year", "analytics_by_year", []),
    ("/api/analytics/monthly-trend?year=2024", "analytics_monthly_trend", []),
    ("/api/analytics/by-theme", "analytics_by_theme", []),
    ("/api/analytics/by-region", "analytics_by_region", []),
    ("/api/analytics/top-organs", "analytics_top_organs", []),
    ("/api/analytics/status", "analytics_status", {}),
], ids=["summary", "by-year", "monthly-trend", "by-theme", "by-region", "top-organs", "status"])
async def test_analytics_does_not_block(client, monkeypatch, path, func, return_value):
    monkeypatch.setattr(f"backend.routes.analytics.{func}", _slow(return_value))

    async def call():
        response = await client.get(path)
        assert response.status_code == 200

    await _assert_health_not_blocked(client, call())


async def test_semantic_search_does_not_block(client, monkeypatch):
    monkeypatch.setattr("backend.services.semantic_search.search_fts", _slow([]))

    async def call():
        response = await client.get("/api/search?q=ayudas%20empresas")
        assert response.status_code == 200

    await _assert_health_not_blocked(client, call())


async def test_keyword_trend_does_not_block(client, monkeypatch):
    monkeypatch.setattr("backend.services.semantic_search.search_fts", _slow([]))

    async def call():
        response = await client.get("/api/analytics/keyword-trend?q=ayudas")
        assert response.status_code == 200

    await _assert_health_not_blocked(client, call())


async def test_grant_detail_does_not_block(client, monkeypatch):
    detail = {"numeroConvocatoria": "123", "descripcion": "Test"}
    monkeypatch.setattr(
        "backend.routes.convocatorias.get_convocatoria_detail_local", _slow(detail)
    )

    async def call():
        response = await client.get("/api/convocatorias/123")
        assert response.status_code == 200
        assert response.json()["numeroConvocatoria"] == "123"

    await _assert_health_not_blocked(client, call())


async def test_grant_page_does_not_block(client, monkeypatch):
    """HTML for /ayuda/{code} (SEO injection) is built off the event loop.

    Calls render_page_with_meta directly: the SPA route is only registered when
    frontend/dist exists, which isn't the case in tests.
    """
    import backend.main as main

    monkeypatch.setattr(main, "get_index_html_with_meta", _slow(("<html>ok</html>", 200)))

    async def call():
        response = await main.render_page_with_meta("ayuda/123")
        assert response.status_code == 200
        assert response.body == b"<html>ok</html>"

    await _assert_health_not_blocked(client, call())


async def test_grant_page_returns_none_without_meta(monkeypatch):
    """No SEO match → None, so the caller falls back to plain index.html."""
    import backend.main as main

    monkeypatch.setattr(main, "get_index_html_with_meta", lambda filename: None)
    assert await main.render_page_with_meta("unknown") is None
