"""Tests for the FAISS vector index service."""

import struct

import faiss
import numpy as np
import pytest

from backend.services.convocatorias_db import (
    init_convocatorias_db,
    sample_embeddings,
    store_embeddings,
    update_convocatoria_detail,
    upsert_convocatorias_list,
)
from backend.services.embeddings import EMBEDDING_DIMS, embedding_to_blob
from backend.services import faiss_index
from backend.services.faiss_index import (
    add_vectors,
    get_stats,
    is_building,
    is_ready,
    load_index_from_db,
    load_or_build,
    reset,
    search,
    sync_from_db,
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


def _insert_many_with_embeddings(db_path: str, count: int) -> None:
    """Insert N convocatorias with detail and random embeddings."""
    import sqlite3

    batch = 500
    for start in range(0, count, batch):
        end = min(start + batch, count)
        nums = [f"L{i:06d}" for i in range(start, end)]
        records = [
            {
                "numeroConvocatoria": num,
                "descripcion": f"Large test convocatoria {num}",
                "fechaRecepcion": "2024-06-01",
                "organo": {"nivel1": "ESTADO", "nivel2": "MIN", "nivel3": None},
            }
            for num in nums
        ]
        upsert_convocatorias_list(records, db_path)
        for num in nums:
            update_convocatoria_detail(
                num, {"presupuestoTotal": 500.0, "abierto": True}, db_path
            )

        # Look up integer IDs for the inserted records
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        placeholders = ",".join("?" for _ in nums)
        rows = conn.execute(
            f"SELECT id, numero_convocatoria FROM convocatorias WHERE numero_convocatoria IN ({placeholders})",
            nums,
        ).fetchall()
        conn.close()

        embeddings = []
        for row in rows:
            vec = np.random.randn(EMBEDDING_DIMS).astype(np.float32)
            vec /= np.linalg.norm(vec)
            embeddings.append((row["id"], embedding_to_blob(vec.tolist())))
        store_embeddings(embeddings, db_path)


class TestSampleEmbeddings:
    """Tests for the sample_embeddings() DB function."""

    def test_returns_requested_count(self, tmp_path):
        path = str(tmp_path / "sample.db")
        init_convocatorias_db(path)
        _insert_many_with_embeddings(path, 100)

        result = sample_embeddings(30, path)
        assert len(result) == 30

    def test_returns_all_if_fewer_than_requested(self, tmp_path):
        path = str(tmp_path / "sample.db")
        init_convocatorias_db(path)
        _insert_many_with_embeddings(path, 5)

        result = sample_embeddings(50, path)
        assert len(result) == 5

    def test_returns_valid_blobs(self, tmp_path):
        path = str(tmp_path / "sample.db")
        init_convocatorias_db(path)
        _insert_many_with_embeddings(path, 10)

        result = sample_embeddings(5, path)
        for conv_id, blob in result:
            assert isinstance(conv_id, int)
            assert isinstance(blob, bytes)
            assert len(blob) == EMBEDDING_DIMS * 4

    def test_empty_db(self, tmp_path):
        path = str(tmp_path / "sample.db")
        init_convocatorias_db(path)

        result = sample_embeddings(10, path)
        assert result == []


def _simple_index_factory(dims, description, metric):
    """Return a simple IVF index suitable for small test datasets.

    The production OPQ64+IVF+PQ64 index needs thousands of vectors for stable
    training. This factory creates a simpler IVFFlat index that works with
    just a few hundred vectors while still exercising the 2-pass code path.
    """
    nlist = 4  # Small number of clusters for test data
    index = faiss.IndexIVFFlat(faiss.IndexFlatIP(dims), dims, nlist, metric)
    return index


class TestLoadIndexTwoPass:
    """Tests for the 2-pass training strategy (datasets >= IVF_THRESHOLD).

    Uses monkeypatch to lower the threshold and use a simpler index factory
    so we don't need 10K+ records for training.
    """

    COUNT = 200

    @pytest.fixture(autouse=True)
    def _lower_threshold(self, monkeypatch):
        monkeypatch.setattr("backend.services.faiss_index._IVF_THRESHOLD", 100)
        monkeypatch.setattr("backend.services.faiss_index._BATCH_SIZE", 50)
        monkeypatch.setattr("faiss.index_factory", _simple_index_factory)

    @pytest.fixture
    def large_db(self, tmp_path):
        path = str(tmp_path / "large.db")
        init_convocatorias_db(path)
        _insert_many_with_embeddings(path, self.COUNT)
        return path

    def test_builds_trained_index(self, large_db):
        load_index_from_db(db_path=large_db)

        stats = get_stats()
        assert stats["ready"] is True
        assert stats["total_vectors"] == self.COUNT

    def test_all_vectors_indexed_not_just_sample(self, large_db):
        """Pass 2 must add ALL vectors, not just the training sample."""
        load_index_from_db(db_path=large_db)
        assert get_stats()["total_vectors"] == self.COUNT

    def test_search_works_after_training(self, large_db):
        load_index_from_db(db_path=large_db)

        query = np.random.randn(EMBEDDING_DIMS).astype(np.float32)
        results = search(query, k=10)

        assert len(results) > 0
        assert len(results) <= 10
        for conv_id, score in results:
            assert isinstance(conv_id, int)
            assert isinstance(score, float)

    def test_known_vector_is_findable(self, tmp_path):
        """Insert a distinctive vector and verify search finds it."""
        import sqlite3

        path = str(tmp_path / "needle.db")
        init_convocatorias_db(path)
        _insert_many_with_embeddings(path, self.COUNT)

        # Insert a "needle" with a distinctive embedding
        records = [{
            "numeroConvocatoria": "NEEDLE",
            "descripcion": "Needle grant",
            "fechaRecepcion": "2024-01-01",
            "organo": {"nivel1": "ESTADO", "nivel2": "MIN", "nivel3": None},
        }]
        upsert_convocatorias_list(records, path)
        update_convocatoria_detail(
            "NEEDLE", {"presupuestoTotal": 1.0, "abierto": True}, path
        )

        # Look up the integer ID
        conn = sqlite3.connect(path)
        needle_id = conn.execute(
            "SELECT id FROM convocatorias WHERE numero_convocatoria = 'NEEDLE'"
        ).fetchone()[0]
        conn.close()

        # Distinctive: all weight on dimension 0
        needle_vec = [0.0] * EMBEDDING_DIMS
        needle_vec[0] = 1.0
        store_embeddings([(needle_id, embedding_to_blob(needle_vec))], path)

        load_index_from_db(db_path=path)

        # Search with a query aligned to dimension 0
        query = np.zeros(EMBEDDING_DIMS, dtype=np.float32)
        query[0] = 1.0
        results = search(query, k=5)

        # The needle should appear with a high score
        top_scores = [(cid, s) for cid, s in results if s > 0.5]
        assert len(top_scores) > 0, f"Expected needle in top results, got: {results}"


def _add_embedded_convocatoria(db_path: str, numero: str, vec: list[float]) -> int:
    """Insert a convocatoria with detail and embedding; return its integer ID."""
    import sqlite3

    upsert_convocatorias_list([{
        "numeroConvocatoria": numero,
        "descripcion": f"Convocatoria {numero}",
        "fechaRecepcion": "2024-01-01",
        "organo": {"nivel1": "ESTADO", "nivel2": "MIN", "nivel3": None},
    }], db_path)
    update_convocatoria_detail(numero, {"presupuestoTotal": 1.0, "abierto": True}, db_path)

    conn = sqlite3.connect(db_path)
    conv_id = conn.execute(
        "SELECT id FROM convocatorias WHERE numero_convocatoria = ?", (numero,)
    ).fetchone()[0]
    conn.close()

    store_embeddings([(conv_id, _make_blob(vec))], db_path)
    return conv_id


def _fail_build(*args, **kwargs):
    raise AssertionError("Index should have been loaded from disk, not rebuilt")


class TestPersistence:
    """Tests for saving the index to disk and loading it at startup."""

    def test_rebuild_saves_index_and_metadata(self, db_with_embeddings, tmp_path):
        index_path = str(tmp_path / "idx" / "faiss.index")
        load_index_from_db(db_path=db_with_embeddings, index_path=index_path)

        import json
        import os

        assert os.path.exists(index_path)
        with open(index_path + ".meta.json") as f:
            meta = json.load(f)
        assert meta["total_vectors"] == 5
        assert meta["dims"] == EMBEDDING_DIMS
        assert meta["embedding_model"] == "text-embedding-3-small"
        assert meta["built_at"]

    def test_load_or_build_builds_when_no_file(self, db_with_embeddings, tmp_path):
        import os

        index_path = str(tmp_path / "faiss.index")
        load_or_build(db_path=db_with_embeddings, index_path=index_path)

        assert is_ready() is True
        assert get_stats()["total_vectors"] == 5
        assert os.path.exists(index_path)

    def test_load_or_build_reads_from_disk_without_rebuilding(
        self, db_with_embeddings, tmp_path, monkeypatch
    ):
        index_path = str(tmp_path / "faiss.index")
        load_index_from_db(db_path=db_with_embeddings, index_path=index_path)
        built_at = get_stats()["built_at"]
        reset()

        monkeypatch.setattr(faiss_index, "_build_from_db", _fail_build)
        load_or_build(db_path=db_with_embeddings, index_path=index_path)

        assert is_ready() is True
        assert get_stats()["total_vectors"] == 5
        assert get_stats()["built_at"] == built_at

        query = np.array([0.0, 1.0, 0.0] + [0.0] * 1533, dtype=np.float32)
        assert search(query, k=1)[0][0] == 2

    def test_load_or_build_adds_embeddings_stored_after_save(
        self, db_with_embeddings, tmp_path, monkeypatch
    ):
        """Embeddings created while the app was down are added on startup."""
        index_path = str(tmp_path / "faiss.index")
        load_index_from_db(db_path=db_with_embeddings, index_path=index_path)
        reset()

        new_id = _add_embedded_convocatoria(db_with_embeddings, "F100", [0.0, 0.0, 0.0, 1.0])

        monkeypatch.setattr(faiss_index, "_build_from_db", _fail_build)
        load_or_build(db_path=db_with_embeddings, index_path=index_path)
        assert get_stats()["total_vectors"] == 6

        query = np.array([0.0, 0.0, 0.0, 1.0] + [0.0] * 1532, dtype=np.float32)
        assert search(query, k=1)[0][0] == new_id

        # The catch-up was saved: a second startup loads 6 vectors directly
        reset()
        load_or_build(db_path=db_with_embeddings, index_path=index_path)
        assert get_stats()["total_vectors"] == 6

    def test_incompatible_metadata_triggers_rebuild(self, db_with_embeddings, tmp_path):
        import json

        index_path = str(tmp_path / "faiss.index")
        load_index_from_db(db_path=db_with_embeddings, index_path=index_path)
        reset()

        meta_path = index_path + ".meta.json"
        with open(meta_path) as f:
            meta = json.load(f)
        meta["embedding_model"] = "some-other-model"
        with open(meta_path, "w") as f:
            json.dump(meta, f)

        load_or_build(db_path=db_with_embeddings, index_path=index_path)

        assert get_stats()["total_vectors"] == 5
        with open(meta_path) as f:
            assert json.load(f)["embedding_model"] == "text-embedding-3-small"

    def test_corrupt_file_triggers_rebuild(self, db_with_embeddings, tmp_path):
        index_path = str(tmp_path / "faiss.index")
        load_index_from_db(db_path=db_with_embeddings, index_path=index_path)
        reset()

        with open(index_path, "wb") as f:
            f.write(b"not a faiss index")

        load_or_build(db_path=db_with_embeddings, index_path=index_path)
        assert is_ready() is True
        assert get_stats()["total_vectors"] == 5

    def test_empty_db_does_not_save(self, tmp_path):
        import os

        path = str(tmp_path / "empty.db")
        init_convocatorias_db(path)
        index_path = str(tmp_path / "faiss.index")

        load_or_build(db_path=path, index_path=index_path)
        assert is_ready() is False
        assert not os.path.exists(index_path)


class TestIncrementalSync:
    """Tests for sync_from_db (incremental add after syncs, no rebuild)."""

    def test_adds_new_embeddings_without_rebuild(
        self, db_with_embeddings, tmp_path, monkeypatch
    ):
        index_path = str(tmp_path / "faiss.index")
        load_index_from_db(db_path=db_with_embeddings, index_path=index_path)

        new_id = _add_embedded_convocatoria(db_with_embeddings, "F200", [0.0, 0.0, 0.0, 1.0])

        monkeypatch.setattr(faiss_index, "_build_from_db", _fail_build)
        added = sync_from_db(db_path=db_with_embeddings, index_path=index_path)

        assert added == 1
        assert get_stats()["total_vectors"] == 6
        query = np.array([0.0, 0.0, 0.0, 1.0] + [0.0] * 1532, dtype=np.float32)
        assert search(query, k=1)[0][0] == new_id

    def test_saves_after_adding(self, db_with_embeddings, tmp_path, monkeypatch):
        index_path = str(tmp_path / "faiss.index")
        load_index_from_db(db_path=db_with_embeddings, index_path=index_path)
        _add_embedded_convocatoria(db_with_embeddings, "F201", [0.0, 0.0, 0.0, 1.0])
        sync_from_db(db_path=db_with_embeddings, index_path=index_path)

        reset()
        monkeypatch.setattr(faiss_index, "_build_from_db", _fail_build)
        load_or_build(db_path=db_with_embeddings, index_path=index_path)
        assert get_stats()["total_vectors"] == 6

    def test_noop_when_up_to_date(self, db_with_embeddings, tmp_path):
        index_path = str(tmp_path / "faiss.index")
        load_index_from_db(db_path=db_with_embeddings, index_path=index_path)

        assert sync_from_db(db_path=db_with_embeddings, index_path=index_path) == 0
        assert get_stats()["total_vectors"] == 5

    def test_skips_when_index_not_loaded(self, db_with_embeddings, tmp_path):
        index_path = str(tmp_path / "faiss.index")
        assert sync_from_db(db_path=db_with_embeddings, index_path=index_path) == 0
        assert is_ready() is False


class TestWriteLock:
    """Builds and updates are serialized by a single write lock."""

    def test_is_building_reflects_write_lock(self):
        assert is_building() is False
        with faiss_index._write_lock:
            assert is_building() is True
        assert is_building() is False

    def test_stats_report_building(self):
        with faiss_index._write_lock:
            assert get_stats()["building"] is True
        assert get_stats()["building"] is False


class TestTrainedIndexPersistence:
    """Save/load and incremental add on a trained IVF index (2-pass path)."""

    COUNT = 200

    @pytest.fixture(autouse=True)
    def _lower_threshold(self, monkeypatch):
        monkeypatch.setattr("backend.services.faiss_index._IVF_THRESHOLD", 100)
        monkeypatch.setattr("backend.services.faiss_index._BATCH_SIZE", 50)
        monkeypatch.setattr("faiss.index_factory", _simple_index_factory)

    def test_round_trip_and_incremental_add(self, tmp_path, monkeypatch):
        path = str(tmp_path / "large.db")
        init_convocatorias_db(path)
        _insert_many_with_embeddings(path, self.COUNT)
        index_path = str(tmp_path / "faiss.index")

        load_index_from_db(db_path=path, index_path=index_path)
        assert get_stats()["total_vectors"] == self.COUNT
        reset()

        monkeypatch.setattr(faiss_index, "_build_from_db", _fail_build)
        load_or_build(db_path=path, index_path=index_path)
        assert get_stats()["total_vectors"] == self.COUNT
        assert faiss.extract_index_ivf(faiss_index._index).nprobe == faiss_index._NPROBE

        needle = [0.0] * EMBEDDING_DIMS
        needle[0] = 1.0
        needle_id = _add_embedded_convocatoria(path, "NEEDLE2", needle[:10])
        assert sync_from_db(db_path=path, index_path=index_path) == 1

        query = np.zeros(EMBEDDING_DIMS, dtype=np.float32)
        query[0] = 1.0
        assert needle_id in [cid for cid, _ in search(query, k=5)]
