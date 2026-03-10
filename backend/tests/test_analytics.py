"""Tests for the analytics routes."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.services.convocatorias_db import (
    init_convocatorias_db,
    rebuild_fts,
    update_convocatoria_detail,
    upsert_convocatorias_list,
)


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """Set up a temporary convocatorias DB for all tests."""
    db_path = str(tmp_path / "test_analytics.db")
    monkeypatch.setattr("backend.services.convocatorias_db._db_path", db_path)

    init_convocatorias_db(db_path)

    # Insert sample data
    records = [
        {
            "numeroConvocatoria": "A001",
            "descripcion": "Ayudas digitalización",
            "fechaRecepcion": "2024-03-15",
            "organo": {"nivel1": "ESTADO", "nivel2": "MINISTERIO INDUSTRIA", "nivel3": None},
        },
        {
            "numeroConvocatoria": "A002",
            "descripcion": "Becas investigación",
            "fechaRecepcion": "2024-06-10",
            "organo": {"nivel1": "ESTADO", "nivel2": "MINISTERIO CIENCIA", "nivel3": None},
        },
        {
            "numeroConvocatoria": "A003",
            "descripcion": "Subvenciones agricultura",
            "fechaRecepcion": "2023-01-01",
            "organo": {"nivel1": "NAVARRA", "nivel2": "GOBIERNO NAVARRA", "nivel3": None},
        },
    ]
    upsert_convocatorias_list(records, db_path)

    # Add detail for analytics queries
    update_convocatoria_detail("A001", {
        "presupuestoTotal": 5000000.0,
        "descripcionFinalidad": "Digital",
        "abierto": True,
        "regiones": [{"id": 1, "descripcion": "MADRID"}],
    }, db_path)
    update_convocatoria_detail("A002", {
        "presupuestoTotal": 2000000.0,
        "descripcionFinalidad": "Ciencia",
        "abierto": False,
        "regiones": [{"id": 2, "descripcion": "CATALUÑA"}],
    }, db_path)
    update_convocatoria_detail("A003", {
        "presupuestoTotal": 1000000.0,
        "descripcionFinalidad": "Agricultura",
        "abierto": True,
        "regiones": [{"id": 3, "descripcion": "NAVARRA"}],
    }, db_path)

    rebuild_fts(db_path)
    return db_path


@pytest.fixture
async def client():
    """Create a test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestAnalyticsSummary:
    @pytest.mark.asyncio
    async def test_summary(self, client):
        resp = await client.get("/api/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["total_budget"] > 0
        assert "open_count" in data
        assert "avg_budget" in data


class TestAnalyticsByYear:
    @pytest.mark.asyncio
    async def test_by_year(self, client):
        resp = await client.get("/api/analytics/by-year")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        years = [d["label"] for d in data]
        assert "2024" in years


class TestAnalyticsMonthlyTrend:
    @pytest.mark.asyncio
    async def test_monthly_trend(self, client):
        resp = await client.get("/api/analytics/monthly-trend?year=2024")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


class TestAnalyticsByTheme:
    @pytest.mark.asyncio
    async def test_by_theme(self, client):
        resp = await client.get("/api/analytics/by-theme")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            assert "label" in data[0]
            assert "count" in data[0]

    @pytest.mark.asyncio
    async def test_by_theme_with_year_filter(self, client):
        resp = await client.get("/api/analytics/by-theme?yearFrom=2024&yearTo=2024")
        assert resp.status_code == 200
        data = resp.json()
        # Should only include 2024 data
        assert isinstance(data, list)


class TestAnalyticsByRegion:
    @pytest.mark.asyncio
    async def test_by_region(self, client):
        resp = await client.get("/api/analytics/by-region")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            labels = [d["label"] for d in data]
            assert any("MADRID" in l for l in labels)


class TestAnalyticsTopOrgans:
    @pytest.mark.asyncio
    async def test_top_organs(self, client):
        resp = await client.get("/api/analytics/top-organs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            assert "label" in data[0]
            assert "count" in data[0]


class TestAnalyticsStatus:
    @pytest.mark.asyncio
    async def test_status(self, client):
        resp = await client.get("/api/analytics/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "open" in data
        assert "closed" in data
        assert data["open"] + data["closed"] == data["total"]
