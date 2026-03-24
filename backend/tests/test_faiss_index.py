"""Tests for the FAISS vector index service."""

import struct

import numpy as np
import pytest

from backend.services.convocatorias_db import (
    init_convocatorias_db,
    store_embeddings,
    update_convocatoria_detail,
    upsert_convocatorias_list,
)
from backend.services.faiss_index import (
    add_vectors,
    get_stats,
    is_ready,
    load_index_from_db,
    reset,
    search,
)


def _make_blob(values: list[float]) -> bytes:
    """Create a fake embedding blob (padded to 1536 dims)."""
    padded = values + [0.0] * (1536 - len(values))
    return struct.pack(f"<{len(padded)}f", *padded)


@pytest.fixture(autouse=True)
def clean_faiss_state():
    """Reset FAISS global state before each test."""
    reset()
    yield
    reset()


@pytest.fixture
def db_with_embeddings(tmp_path):
    """Create a test DB with embedded convocatorias."""
    path = str(tmp_path / "test_faiss.db")
    init_convocatorias_db(path)

    records = [
        {
            "numeroConvocatoria": f"F{i:03d}",
            "descripcion": f"Test convocatoria {i}",
            "fechaRecepcion": "2024-01-01",
            "organo": {"nivel1": "ESTADO", "nivel2": "MINISTERIO", "nivel3": None},
        }
        for i in range(1, 6)
    ]
    upsert_convocatorias_list(records, path)

    for i in range(1, 6):
        update_convocatoria_detail(f"F{i:03d}", {
            "presupuestoTotal": 100000.0,
            "abierto": True,
        }, path)

    # Store embeddings — each one points in a different direction
    embeddings = [
        (1, _make_blob([1.0, 0.0, 0.0])),
        (2, _make_blob([0.0, 1.0, 0.0])),
        (3, _make_blob([0.0, 0.0, 1.0])),
        (4, _make_blob([0.7, 0.7, 0.0])),
        (5, _make_blob([0.5, 0.5, 0.5])),
    ]
    store_embeddings(embeddings, path)

    return path


class TestFaissIndex:
    """Tests for FAISS index lifecycle."""

    def test_not_ready_before_load(self):
        assert is_ready() is False

    def test_not_ready_returns_empty_search(self):
        query = np.array([1.0] + [0.0] * 1535, dtype=np.float32)
        assert search(query) == []

    def test_load_and_search(self, db_with_embeddings):
        load_index_from_db(db_path=db_with_embeddings)
        assert is_ready() is True

        # Search for vector close to [1, 0, 0]
        query = np.array([1.0, 0.0, 0.0] + [0.0] * 1533, dtype=np.float32)
        results = search(query, k=3)

        assert len(results) == 3
        # First result should be ID 1 (exact match to [1, 0, 0])
        assert results[0][0] == 1
        assert results[0][1] > 0.9  # high similarity

    def test_search_ranking(self, db_with_embeddings):
        load_index_from_db(db_path=db_with_embeddings)

        # Search for [0, 1, 0] — should match ID 2 best
        query = np.array([0.0, 1.0, 0.0] + [0.0] * 1533, dtype=np.float32)
        results = search(query, k=5)

        assert results[0][0] == 2  # exact match

    def test_get_stats(self, db_with_embeddings):
        assert get_stats()["ready"] is False

        load_index_from_db(db_path=db_with_embeddings)
        stats = get_stats()
        assert stats["ready"] is True
        assert stats["total_vectors"] == 5

    def test_add_vectors(self, db_with_embeddings):
        load_index_from_db(db_path=db_with_embeddings)
        assert get_stats()["total_vectors"] == 5

        # Add a new vector
        new_vec = np.array([[0.0, 0.0, 1.0] + [0.0] * 1533], dtype=np.float32)
        add_vectors([99], new_vec)

        assert get_stats()["total_vectors"] == 6

        # New vector should be searchable
        query = np.array([0.0, 0.0, 1.0] + [0.0] * 1533, dtype=np.float32)
        results = search(query, k=2)
        result_ids = [r[0] for r in results]
        assert 99 in result_ids

    def test_empty_db_no_crash(self, tmp_path):
        """Loading from a DB with no embeddings should not crash."""
        path = str(tmp_path / "empty.db")
        init_convocatorias_db(path)

        load_index_from_db(db_path=path)
        assert is_ready() is False
