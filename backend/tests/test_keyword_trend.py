"""Tests for keyword trend analytics (aggregate_by_year_for_ids + keyword_trend + endpoint)."""

import struct
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.services.convocatorias_db import (
    aggregate_by_year_for_ids,
    init_convocatorias_db,
    rebuild_fts,
    store_embeddings,
    update_convocatoria_detail,
    upsert_convocatorias_list,
)
from backend.services.semantic_search import keyword_trend


def _make_blob(values: list[float]) -> bytes:
    """Create a fake embedding blob from float values (padded to 1536)."""
    padded = values + [0.0] * (1536 - len(values))
    return struct.pack(f"<{len(padded)}f", *padded)


@pytest.fixture
def db_path(tmp_path):
    """Create and populate a test DB with embeddings."""
    path = str(tmp_path / "test_keyword_trend.db")
    init_convocatorias_db(path)

    records = [
        {
            "numeroConvocatoria": "K001",
            "descripcion": "Ayudas para agricultura ecologica",
            "fechaRecepcion": "2023-05-10",
            "organo": {"nivel1": "ESTADO", "nivel2": "MIN AGRICULTURA", "nivel3": None},
        },
        {
            "numeroConvocatoria": "K002",
            "descripcion": "Subvenciones agricultura sostenible",
            "fechaRecepcion": "2024-03-15",
            "organo": {"nivel1": "NAVARRA", "nivel2": "GOB NAVARRA", "nivel3": None},
        },
        {
            "numeroConvocatoria": "K003",
            "descripcion": "Becas digitalización pymes",
            "fechaRecepcion": "2024-06-10",
            "organo": {"nivel1": "ESTADO", "nivel2": "MIN INDUSTRIA", "nivel3": None},
        },
    ]
    upsert_convocatorias_list(records, path)

    for num, finalidad, budget, abierto in [
        ("K001", "Agricultura y alimentación", 1000000.0, True),
        ("K002", "Agricultura y alimentación", 2000000.0, True),
        ("K003", "Transformación digital", 500000.0, False),
    ]:
        update_convocatoria_detail(num, {
            "presupuestoTotal": budget,
            "descripcionFinalidad": finalidad,
            "abierto": abierto,
        }, path)

    rebuild_fts(path)

    # Embeddings: K001/K002 similar (agriculture), K003 different (digital)
    emb_agri = _make_blob([0.9, 0.1, 0.0])
    emb_digi = _make_blob([0.0, 0.1, 0.9])

    store_embeddings([(1, emb_agri), (2, emb_agri), (3, emb_digi)], path)
    return path


class TestAggregateByYearForIds:
    """Tests for aggregate_by_year_for_ids()."""

    def test_aggregates_correctly(self, db_path):
        # IDs 1 and 2 are agriculture (2023 and 2024)
        result = aggregate_by_year_for_ids([1, 2], db_path)
        assert len(result) == 2
        years = {r["year"]: r for r in result}
        assert "2023" in years
        assert "2024" in years
        assert years["2023"]["count"] == 1
        assert years["2023"]["budget"] == 1000000.0
        assert years["2024"]["count"] == 1
        assert years["2024"]["budget"] == 2000000.0

    def test_all_ids(self, db_path):
        result = aggregate_by_year_for_ids([1, 2, 3], db_path)
        years = {r["year"]: r for r in result}
        assert years["2024"]["count"] == 2  # K002 + K003

    def test_empty_ids(self, db_path):
        result = aggregate_by_year_for_ids([], db_path)
        assert result == []

    def test_nonexistent_ids(self, db_path):
        result = aggregate_by_year_for_ids([999, 888], db_path)
        assert result == []

    def test_large_batch(self, db_path):
        """Test with more than 500 IDs to verify batching works."""
        # Only 3 exist, but we pass 600 IDs
        ids = list(range(1, 601))
        result = aggregate_by_year_for_ids(ids, db_path)
        # Should still only find the 3 that exist
        total = sum(r["count"] for r in result)
        assert total == 3


class TestKeywordTrend:
    """Tests for keyword_trend() with mocked OpenAI."""

    @pytest.mark.asyncio
    async def test_returns_trend_data(self, db_path):
        mock_embedding = [0.9, 0.1, 0.0] + [0.0] * 1533

        with patch("backend.services.semantic_search.search_fts") as mock_fts, \
             patch("backend.services.semantic_search.get_recent_with_embeddings") as mock_recent, \
             patch("backend.services.semantic_search.aggregate_by_year_for_ids") as mock_agg, \
             patch("backend.services.semantic_search.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:

            mock_fts.return_value = [
                {
                    "id": 1, "numero_convocatoria": "K001",
                    "descripcion": "Ayudas agricultura",
                    "fecha_recepcion": "2023-05-10",
                    "nivel1": "ESTADO", "nivel2": "MIN", "nivel3": None,
                    "presupuesto_total": 1000000.0, "abierto": 1,
                    "embedding": _make_blob([0.9, 0.1, 0.0]),
                    "descripcion_leng": None, "descripcion_finalidad": None,
                    "finalidad_id": None, "fecha_inicio_solicitud": None,
                    "fecha_fin_solicitud": None, "text_inicio": None, "text_fin": None,
                },
            ]
            mock_recent.return_value = [
                {
                    "id": 2, "numero_convocatoria": "K002",
                    "descripcion": "Subvenciones agricultura",
                    "fecha_recepcion": "2024-03-15",
                    "nivel1": "NAVARRA", "nivel2": "GOB", "nivel3": None,
                    "presupuesto_total": 2000000.0, "abierto": 1,
                    "embedding": _make_blob([0.85, 0.15, 0.0]),
                    "descripcion_leng": None, "descripcion_finalidad": None,
                    "finalidad_id": None, "fecha_inicio_solicitud": None,
                    "fecha_fin_solicitud": None, "text_inicio": None, "text_fin": None,
                },
            ]
            mock_embed.return_value = [mock_embedding]
            mock_agg.return_value = [
                {"year": "2023", "count": 1, "budget": 1000000.0},
                {"year": "2024", "count": 1, "budget": 2000000.0},
            ]

            result = await keyword_trend("agricultura")

        assert result["query"] == "agricultura"
        assert result["total_matches"] == 2
        assert len(result["by_year"]) == 2
        mock_agg.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_query(self):
        result = await keyword_trend("")
        assert result["total_matches"] == 0
        assert result["by_year"] == []

    @pytest.mark.asyncio
    async def test_fallback_on_embedding_error(self, db_path):
        with patch("backend.services.semantic_search.search_fts") as mock_fts, \
             patch("backend.services.semantic_search.get_recent_with_embeddings") as mock_recent, \
             patch("backend.services.semantic_search.aggregate_by_year_for_ids") as mock_agg, \
             patch("backend.services.semantic_search.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:

            mock_fts.return_value = [
                {
                    "id": 1, "numero_convocatoria": "K001",
                    "descripcion": "Test", "fecha_recepcion": "2024-01-01",
                    "nivel1": "ESTADO", "nivel2": "MIN", "nivel3": None,
                    "presupuesto_total": 100.0, "abierto": 1,
                    "embedding": _make_blob([1.0, 0.0, 0.0]),
                    "descripcion_leng": None, "descripcion_finalidad": None,
                    "finalidad_id": None, "fecha_inicio_solicitud": None,
                    "fecha_fin_solicitud": None, "text_inicio": None, "text_fin": None,
                },
            ]
            mock_recent.return_value = []
            mock_embed.side_effect = ValueError("No API key")
            mock_agg.return_value = [{"year": "2024", "count": 1, "budget": 100.0}]

            result = await keyword_trend("test")

        # Should still return FTS-based results
        assert result["total_matches"] == 1
        assert len(result["by_year"]) == 1


class TestKeywordTrendEndpoint:
    """Tests for GET /api/analytics/keyword-trend."""

    @pytest.fixture(autouse=True)
    def setup(self, db_path, monkeypatch):
        monkeypatch.setattr("backend.services.convocatorias_db._db_path", db_path)

    @pytest.fixture
    async def client(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.mark.asyncio
    async def test_endpoint_returns_200(self, client):
        with patch("backend.routes.analytics.keyword_trend", new_callable=AsyncMock) as mock_kt:
            mock_kt.return_value = {
                "query": "agricultura",
                "total_matches": 5,
                "by_year": [{"year": "2024", "count": 3, "budget": 100.0}],
            }
            resp = await client.get("/api/analytics/keyword-trend?q=agricultura")

        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "agricultura"
        assert data["total_matches"] == 5
        assert len(data["by_year"]) == 1

    @pytest.mark.asyncio
    async def test_endpoint_caches_result(self, client):
        with patch("backend.routes.analytics.keyword_trend", new_callable=AsyncMock) as mock_kt:
            mock_kt.return_value = {
                "query": "test_cache",
                "total_matches": 1,
                "by_year": [],
            }
            # First call
            await client.get("/api/analytics/keyword-trend?q=test_cache")
            # Second call should use cache
            await client.get("/api/analytics/keyword-trend?q=test_cache")

        assert mock_kt.call_count == 1
