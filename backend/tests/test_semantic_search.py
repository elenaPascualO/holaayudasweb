"""Tests for the hybrid semantic search service (FTS5 + FAISS + RRF)."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.convocatorias_db import (
    init_convocatorias_db,
    rebuild_fts,
    update_convocatoria_detail,
    upsert_convocatorias_list,
)
from backend.services.semantic_search import (
    reciprocal_rank_fusion,
    semantic_search,
)


def _make_fts_result(
    id: int,
    num: str,
    desc: str,
    fecha: str = "2024-03-15",
    nivel1: str = "ESTADO",
    nivel2: str = "MINISTERIO",
    abierto: int = 1,
) -> dict:
    """Create a mock FTS result dict."""
    return {
        "id": id,
        "numero_convocatoria": num,
        "descripcion": desc,
        "descripcion_leng": None,
        "fecha_recepcion": fecha,
        "nivel1": nivel1,
        "nivel2": nivel2,
        "nivel3": None,
        "presupuesto_total": 1000000.0,
        "abierto": abierto,
        "descripcion_finalidad": None,
        "finalidad_id": None,
        "fecha_inicio_solicitud": None,
        "fecha_fin_solicitud": None,
        "text_inicio": None,
        "text_fin": None,
        "regiones_json": None,
    }


@pytest.fixture
def db_path(tmp_path):
    """Create and populate a test DB."""
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
    ]
    upsert_convocatorias_list(records, path)

    for num, finalidad, abierto in [
        ("S001", "Transformación digital", True),
        ("S002", "Investigación en salud", False),
    ]:
        update_convocatoria_detail(num, {
            "presupuestoTotal": 1000000.0,
            "descripcionFinalidad": finalidad,
            "abierto": abierto,
        }, path)

    rebuild_fts(path)
    return path


class TestRRF:
    """Tests for reciprocal_rank_fusion()."""

    def test_single_list(self):
        result = reciprocal_rank_fusion([[10, 20, 30]], k=60)
        assert result[0][0] == 10  # rank 1 = highest score
        assert result[1][0] == 20
        assert result[2][0] == 30

    def test_overlapping_lists_boosted(self):
        # Doc 20 appears in both lists → should rank highest
        result = reciprocal_rank_fusion(
            [[10, 20, 30], [20, 40, 50]], k=60
        )
        scores = {doc_id: score for doc_id, score in result}
        assert scores[20] > scores[10]  # 20 is in both lists
        assert scores[20] > scores[40]

    def test_disjoint_lists(self):
        result = reciprocal_rank_fusion(
            [[1, 2], [3, 4]], k=60
        )
        # All docs should have equal scores at same rank positions
        scores = {doc_id: score for doc_id, score in result}
        assert scores[1] == scores[3]  # both rank 1 in their list
        assert scores[2] == scores[4]  # both rank 2

    def test_empty_lists(self):
        result = reciprocal_rank_fusion([], k=60)
        assert result == []


class TestSemanticSearch:
    """Tests for semantic_search() with mocked FTS + FAISS."""

    @pytest.mark.asyncio
    async def test_hybrid_fts_and_faiss(self, db_path):
        """Both FTS and FAISS return results — RRF fuses them."""
        fts_results = [
            _make_fts_result(1, "S001", "Ayudas digitalización pymes"),
            _make_fts_result(2, "S002", "Becas investigación"),
        ]

        with patch("backend.services.semantic_search.search_fts") as mock_fts, \
             patch("backend.services.semantic_search.faiss_index") as mock_faiss, \
             patch("backend.services.semantic_search._embed_query", new_callable=AsyncMock) as mock_embed, \
             patch("backend.services.semantic_search.get_convocatorias_by_ids") as mock_get:

            mock_fts.return_value = fts_results
            mock_faiss.is_ready.return_value = True
            mock_embed.return_value = None  # Will use FAISS mock directly
            # Since _embed_query returns None, FAISS won't be called
            # Let's make it return a vector instead
            import numpy as np
            mock_embed.return_value = np.array([1.0] + [0.0] * 1535, dtype=np.float32)
            mock_faiss.search.return_value = [(1, 0.9), (3, 0.5)]  # ID 3 is FAISS-only
            mock_get.return_value = {
                3: _make_fts_result(3, "S003", "Subvenciones agricultura"),
            }

            result = await semantic_search("digitalización", top_k=10)

        assert "content" in result
        assert len(result["content"]) == 3
        # ID 1 appears in both lists → should rank first
        assert result["content"][0]["numeroConvocatoria"] == "S001"

    @pytest.mark.asyncio
    async def test_fts_only_when_faiss_not_ready(self, db_path):
        """When FAISS is not ready, falls back to FTS-only."""
        fts_results = [
            _make_fts_result(1, "S001", "Test grant"),
        ]

        with patch("backend.services.semantic_search.search_fts") as mock_fts, \
             patch("backend.services.semantic_search.faiss_index") as mock_faiss:

            mock_fts.return_value = fts_results
            mock_faiss.is_ready.return_value = False

            result = await semantic_search("test query")

        assert len(result["content"]) == 1
        assert result["content"][0]["numeroConvocatoria"] == "S001"

    @pytest.mark.asyncio
    async def test_faiss_only_when_fts_empty(self, db_path):
        """When FTS returns nothing but FAISS has results."""
        import numpy as np

        with patch("backend.services.semantic_search.search_fts") as mock_fts, \
             patch("backend.services.semantic_search.faiss_index") as mock_faiss, \
             patch("backend.services.semantic_search._embed_query", new_callable=AsyncMock) as mock_embed, \
             patch("backend.services.semantic_search.get_convocatorias_by_ids") as mock_get:

            mock_fts.return_value = []
            mock_faiss.is_ready.return_value = True
            mock_embed.return_value = np.array([1.0] + [0.0] * 1535, dtype=np.float32)
            mock_faiss.search.return_value = [(1, 0.8)]
            mock_get.return_value = {
                1: _make_fts_result(1, "S001", "Semantic match only"),
            }

            result = await semantic_search("something completely different")

        assert len(result["content"]) == 1
        assert result["content"][0]["numeroConvocatoria"] == "S001"

    @pytest.mark.asyncio
    async def test_empty_query(self, db_path):
        result = await semantic_search("")
        assert result["content"] == []
        assert result["totalElements"] == 0

    @pytest.mark.asyncio
    async def test_no_results_from_either(self, db_path):
        """Both FTS and FAISS return nothing → empty response."""
        import numpy as np

        with patch("backend.services.semantic_search.search_fts") as mock_fts, \
             patch("backend.services.semantic_search.faiss_index") as mock_faiss, \
             patch("backend.services.semantic_search._embed_query", new_callable=AsyncMock) as mock_embed:

            mock_fts.return_value = []
            mock_faiss.is_ready.return_value = True
            mock_embed.return_value = np.array([1.0] + [0.0] * 1535, dtype=np.float32)
            mock_faiss.search.return_value = []  # No results above threshold

            result = await semantic_search("galizuela")

        assert result["content"] == []
        assert result["totalElements"] == 0

    @pytest.mark.asyncio
    async def test_similarity_threshold_filters_low_scores(self, db_path):
        """FAISS results below threshold are excluded."""
        import numpy as np

        with patch("backend.services.semantic_search.search_fts") as mock_fts, \
             patch("backend.services.semantic_search.faiss_index") as mock_faiss, \
             patch("backend.services.semantic_search._embed_query", new_callable=AsyncMock) as mock_embed, \
             patch("backend.services.semantic_search.get_convocatorias_by_ids") as mock_get:

            mock_fts.return_value = []
            mock_faiss.is_ready.return_value = True
            mock_embed.return_value = np.array([1.0] + [0.0] * 1535, dtype=np.float32)
            # One above threshold, one below
            mock_faiss.search.return_value = [(1, 0.5), (2, 0.1)]
            mock_get.return_value = {
                1: _make_fts_result(1, "S001", "Relevant"),
            }

            result = await semantic_search("query", similarity_threshold=0.25)

        # Only ID 1 (score 0.5) should pass, not ID 2 (score 0.1)
        assert len(result["content"]) == 1
        assert result["content"][0]["numeroConvocatoria"] == "S001"

    @pytest.mark.asyncio
    async def test_fallback_on_embedding_error(self, db_path):
        """When embedding fails, returns FTS results without scores."""
        with patch("backend.services.semantic_search.search_fts") as mock_fts, \
             patch("backend.services.semantic_search.faiss_index") as mock_faiss, \
             patch("backend.services.semantic_search._embed_query", new_callable=AsyncMock) as mock_embed:

            mock_fts.return_value = [
                _make_fts_result(1, "S001", "Test"),
            ]
            mock_faiss.is_ready.return_value = True
            mock_embed.return_value = None  # Embedding failed

            result = await semantic_search("test query")

        # Should still return FTS results (FAISS skipped)
        assert len(result["content"]) == 1
        assert result["content"][0]["numeroConvocatoria"] == "S001"

    @pytest.mark.asyncio
    async def test_response_format_compatible(self, db_path):
        """Response format matches BDNS pagination structure."""
        with patch("backend.services.semantic_search.search_fts") as mock_fts, \
             patch("backend.services.semantic_search.faiss_index") as mock_faiss:

            mock_fts.return_value = [
                _make_fts_result(1, "S001", "Test grant"),
            ]
            mock_faiss.is_ready.return_value = False

            result = await semantic_search("test")

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
