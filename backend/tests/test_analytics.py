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
        "finalidad": {"id": 10},
        "abierto": True,
        "regiones": [{"id": 1, "codigo": "ES30", "descripcion": "MADRID"}],
    }, db_path)
    update_convocatoria_detail("A002", {
        "presupuestoTotal": 2000000.0,
        "descripcionFinalidad": "Ciencia",
        "finalidad": {"id": 20},
        "abierto": False,
        "regiones": [{"id": 2, "codigo": "ES51", "descripcion": "CATALUÑA"}],
    }, db_path)
    update_convocatoria_detail("A003", {
        "presupuestoTotal": 1000000.0,
        "descripcionFinalidad": "Agricultura",
        "finalidad": {"id": 30},
        "abierto": True,
        "regiones": [{"id": 3, "codigo": "ES22", "descripcion": "NAVARRA"}],
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

    @pytest.mark.asyncio
    async def test_by_year_includes_tax_revenue(self, client):
        """Each year entry should include tax_revenue and tax_source_url."""
        resp = await client.get("/api/analytics/by-year")
        assert resp.status_code == 200
        data = resp.json()
        entry_2024 = next(d for d in data if d["label"] == "2024")
        assert "tax_revenue" in entry_2024
        assert "tax_source_url" in entry_2024
        assert entry_2024["tax_revenue"] == 294_734_000_000
        assert "agenciatributaria" in entry_2024["tax_source_url"]

    @pytest.mark.asyncio
    async def test_by_year_tax_revenue_null_for_unknown_year(self, client, setup_db):
        """Tax revenue should be None for years without AEAT data."""
        from backend.services.cache import cache
        from backend.services.convocatorias_db import upsert_convocatorias_list, update_convocatoria_detail
        db_path = setup_db
        upsert_convocatorias_list([{
            "numeroConvocatoria": "F001",
            "descripcion": "Future grant",
            "fechaRecepcion": "2030-01-01",
            "organo": {"nivel1": "ESTADO", "nivel2": "MIN", "nivel3": None},
        }], db_path)
        update_convocatoria_detail("F001", {
            "presupuestoTotal": 100.0,
            "descripcionFinalidad": "Test",
            "abierto": True,
        }, db_path)

        cache._store.pop("analytics:by-year", None)
        resp = await client.get("/api/analytics/by-year")
        data = resp.json()
        entry_2030 = next((d for d in data if d["label"] == "2030"), None)
        assert entry_2030 is not None
        assert entry_2030["tax_revenue"] is None
        assert entry_2030["tax_source_url"] is None


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
    async def test_by_theme_returns_code(self, client):
        """Theme entries should include finalidad_id as 'code' for chart drill-down."""
        resp = await client.get("/api/analytics/by-theme")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        # Every entry should have a code field
        for entry in data:
            assert "code" in entry
        # Verify specific codes from fixture
        codes = {d["label"]: d["code"] for d in data}
        assert codes["Digital"] == 10
        assert codes["Ciencia"] == 20

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

    @pytest.mark.asyncio
    async def test_by_region_returns_code(self, client):
        """Region entries should include region codigo as 'code' for chart drill-down."""
        resp = await client.get("/api/analytics/by-region")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        # Every entry should have a code field
        for entry in data:
            assert "code" in entry
        # Verify specific codes from fixture
        codes = {d["label"]: d["code"] for d in data}
        assert codes["MADRID"] == "ES30"
        assert codes["CATALUÑA"] == "ES51"


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
