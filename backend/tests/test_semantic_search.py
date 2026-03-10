"""Tests for the semantic search service."""

import json
import struct
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from backend.services.convocatorias_db import (
    init_convocatorias_db,
    rebuild_fts,
    store_embeddings,
    update_convocatoria_detail,
    upsert_convocatorias_list,
)
from backend.services.semantic_search import (
    _cosine_similarity_batch,
    semantic_search,
)


def _make_blob(values: list[float]) -> bytes:
    """Create a fake embedding blob from float values (padded to 1536)."""
    padded = values + [0.0] * (1536 - len(values))
    return struct.pack(f"<{len(padded)}f", *padded)


@pytest.fixture
def db_path(tmp_path):
    """Create and populate a test DB with embeddings."""
    path = str(tmp_path / "test_semantic.db")
    init_convocatorias_db(path)

    records = [
        {
            "numeroConvocatoria": "S001",
            "descripcion": "Ayudas para digitalización de pymes",
            "fechaRecepcion": "2024-03-15",
            "organo": {"nivel1": "ESTADO", "nivel2": "MINISTERIO INDUSTRIA", "nivel3": None},
        },
        {
            "numeroConvocatoria": "S002",
            "descripcion": "Becas de investigación diabetes",
            "fechaRecepcion": "2024-02-10",
            "organo": {"nivel1": "ESTADO", "nivel2": "MINISTERIO CIENCIA", "nivel3": None},
        },
        {
            "numeroConvocatoria": "S003",
            "descripcion": "Subvenciones agricultura sostenible",
            "fechaRecepcion": "2023-01-01",
            "organo": {"nivel1": "NAVARRA", "nivel2": "GOBIERNO NAVARRA", "nivel3": None},
        },
    ]
    upsert_convocatorias_list(records, path)

    # Add detail
    for num, finalidad, abierto in [
        ("S001", "Transformación digital", True),
        ("S002", "Investigación en salud", False),
        ("S003", "Agricultura y alimentación", True),
    ]:
        update_convocatoria_detail(num, {
            "presupuestoTotal": 1000000.0,
            "descripcionFinalidad": finalidad,
            "abierto": abierto,
        }, path)

    rebuild_fts(path)

    # Store embeddings — make S001 similar to "digital", S002 to "diabetes"
    emb1 = _make_blob([0.9, 0.1, 0.0])  # digital-like
    emb2 = _make_blob([0.1, 0.9, 0.0])  # health-like
    emb3 = _make_blob([0.0, 0.1, 0.9])  # agriculture-like

    store_embeddings([(1, emb1), (2, emb2), (3, emb3)], path)

    return path


class TestCosineSimilarity:
    """Tests for _cosine_similarity_batch()."""

    def test_identical_vectors(self):
        q = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        c = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
        scores = _cosine_similarity_batch(q, c)
        assert scores[0] == pytest.approx(1.0, abs=1e-5)

    def test_orthogonal_vectors(self):
        q = np.array([1.0, 0.0], dtype=np.float32)
        c = np.array([[0.0, 1.0]], dtype=np.float32)
        scores = _cosine_similarity_batch(q, c)
        assert scores[0] == pytest.approx(0.0, abs=1e-5)

    def test_ranking_order(self):
        q = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        c = np.array([
            [0.9, 0.1, 0.0],  # most similar
            [0.5, 0.5, 0.0],  # medium
            [0.0, 0.1, 0.9],  # least similar
        ], dtype=np.float32)
        scores = _cosine_similarity_batch(q, c)
        assert scores[0] > scores[1] > scores[2]


class TestSemanticSearch:
    """Tests for semantic_search() with mocked OpenAI."""

    @pytest.mark.asyncio
    async def test_returns_results_with_scores(self, db_path):
        # Mock OpenAI to return a "digital-like" embedding
        mock_embedding = [0.9, 0.1, 0.0] + [0.0] * 1533

        with patch("backend.services.semantic_search.search_fts") as mock_fts, \
             patch("backend.services.semantic_search.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:

            # FTS returns all 3 candidates
            mock_fts.return_value = [
                {
                    "id": 1, "numero_convocatoria": "S001",
                    "descripcion": "Ayudas para digitalización de pymes",
                    "descripcion_leng": None,
                    "fecha_recepcion": "2024-03-15",
                    "nivel1": "ESTADO", "nivel2": "MINISTERIO INDUSTRIA", "nivel3": None,
                    "presupuesto_total": 1000000.0, "abierto": 1,
                    "embedding": _make_blob([0.9, 0.1, 0.0]),
                    "descripcion_finalidad": "Digital", "finalidad_id": 10,
                    "fecha_inicio_solicitud": None, "fecha_fin_solicitud": None,
                    "text_inicio": None, "text_fin": None,
                },
                {
                    "id": 2, "numero_convocatoria": "S002",
                    "descripcion": "Becas de investigación diabetes",
                    "descripcion_leng": None,
                    "fecha_recepcion": "2024-02-10",
                    "nivel1": "ESTADO", "nivel2": "MINISTERIO CIENCIA", "nivel3": None,
                    "presupuesto_total": 1000000.0, "abierto": 0,
                    "embedding": _make_blob([0.1, 0.9, 0.0]),
                    "descripcion_finalidad": "Salud", "finalidad_id": 20,
                    "fecha_inicio_solicitud": None, "fecha_fin_solicitud": None,
                    "text_inicio": None, "text_fin": None,
                },
            ]
            mock_embed.return_value = [mock_embedding]

            result = await semantic_search("digitalización pymes", top_k=2)

        assert "content" in result
        assert len(result["content"]) == 2
        # S001 should rank first (more similar to digital)
        assert result["content"][0]["numeroConvocatoria"] == "S001"
        assert result["content"][0]["_score"] > result["content"][1]["_score"]

    @pytest.mark.asyncio
    async def test_empty_query(self, db_path):
        result = await semantic_search("")
        assert result["content"] == []
        assert result["totalElements"] == 0

    @pytest.mark.asyncio
    async def test_fallback_on_embedding_error(self, db_path):
        with patch("backend.services.semantic_search.search_fts") as mock_fts, \
             patch("backend.services.semantic_search.get_recent_with_embeddings") as mock_recent, \
             patch("backend.services.semantic_search.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:

            mock_fts.return_value = [
                {
                    "id": 1, "numero_convocatoria": "S001",
                    "descripcion": "Test",
                    "descripcion_leng": None,
                    "fecha_recepcion": "2024-03-15",
                    "nivel1": "ESTADO", "nivel2": "MIN", "nivel3": None,
                    "presupuesto_total": None, "abierto": 1,
                    "embedding": None,
                    "descripcion_finalidad": None, "finalidad_id": None,
                    "fecha_inicio_solicitud": None, "fecha_fin_solicitud": None,
                    "text_inicio": None, "text_fin": None,
                },
            ]
            mock_recent.return_value = []
            mock_embed.side_effect = ValueError("No API key")

            result = await semantic_search("test query")

        # Should still return FTS results without scores
        assert len(result["content"]) == 1
        assert result["content"][0]["numeroConvocatoria"] == "S001"

    @pytest.mark.asyncio
    async def test_response_format_compatible(self, db_path):
        with patch("backend.services.semantic_search.search_fts") as mock_fts, \
             patch("backend.services.semantic_search.get_recent_with_embeddings") as mock_recent, \
             patch("backend.services.semantic_search.generate_embeddings_batch", new_callable=AsyncMock) as mock_embed:

            mock_fts.return_value = [
                {
                    "id": 1, "numero_convocatoria": "S001",
                    "descripcion": "Test grant",
                    "descripcion_leng": None,
                    "fecha_recepcion": "2024-03-15",
                    "nivel1": "ESTADO", "nivel2": "MINISTERIO", "nivel3": None,
                    "presupuesto_total": 500000.0, "abierto": 1,
                    "embedding": _make_blob([1.0, 0.0, 0.0]),
                    "descripcion_finalidad": None, "finalidad_id": None,
                    "fecha_inicio_solicitud": None, "fecha_fin_solicitud": None,
                    "text_inicio": None, "text_fin": None,
                },
            ]
            mock_recent.return_value = []
            mock_embed.return_value = [[1.0, 0.0, 0.0] + [0.0] * 1533]

            result = await semantic_search("test")

        # Verify BDNS-compatible format
        assert "content" in result
        assert "totalElements" in result
        assert "totalPages" in result
        assert "number" in result
        assert "size" in result

        item = result["content"][0]
        assert "numeroConvocatoria" in item
        assert "descripcion" in item
        assert "fechaRecepcion" in item
        assert "organo" in item
        assert "nivel1" in item["organo"]
