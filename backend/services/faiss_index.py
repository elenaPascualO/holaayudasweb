"""FAISS in-memory vector index for semantic search over all convocatorias.

The index is persisted to disk so restarts don't need to rebuild it:

- Startup (`load_or_build`): read the index from disk in seconds, then add any
  embeddings that are in SQLite but not yet in the index. Full build only if
  there is no usable file.
- After a sync (`sync_from_db`): add the new embeddings incrementally (the
  index is already trained, so no retraining is needed) and save.
- Manual retrain (`load_index_from_db`): full build from SQLite, then save.

SQLite is the source of truth; the file on disk is only a cache. All index
mutations are serialized by `_write_lock`, so two builds can never run at
the same time (two concurrent builds don't fit in the server's memory).
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

import faiss
import numpy as np

from backend.config import FAISS_INDEX_PATH
from backend.services.embeddings import EMBEDDING_DIMS, EMBEDDING_MODEL, blob_to_embedding

logger = logging.getLogger(__name__)

# Global index state
_index: faiss.Index | None = None
_ready: bool = False
_built_at: str | None = None
_lock = threading.Lock()  # Guards reads/writes of the live index (search vs add/swap)
_write_lock = threading.Lock()  # Serializes build / incremental add / save

# Minimum vectors to justify training an IVF index
_IVF_THRESHOLD = 10_000
_BATCH_SIZE = 10_000
# Vectors added per locked step, so searches aren't blocked for long
_ADD_CHUNK_SIZE = 5_000
_NPROBE = 32
# Bump when the on-disk format or index recipe changes to force a rebuild
_FORMAT_VERSION = 1


def is_ready() -> bool:
    """Check if FAISS index is loaded and ready for queries."""
    return _ready


def is_building() -> bool:
    """Check if a build, incremental update or save is in progress."""
    return _write_lock.locked()


def _resolve_index_path(db_path: str | None, index_path: str | None) -> str:
    """Return the index file path.

    When only db_path is overridden (tests), keep the index next to that DB.
    """
    if index_path:
        return index_path
    if db_path:
        return str(Path(db_path).parent / "faiss.index")
    return FAISS_INDEX_PATH


def _meta_path(index_path: str) -> str:
    """Return the path of the metadata file that accompanies the index."""
    return index_path + ".meta.json"


def _now_iso() -> str:
    """Return the current UTC time as ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def _configure(index: faiss.Index) -> None:
    """Apply search-time parameters (nprobe) to IVF indexes."""
    try:
        faiss.extract_index_ivf(index).nprobe = _NPROBE
    except RuntimeError:
        pass  # Flat index (small datasets) has no IVF layer


def _blobs_to_arrays(batch: list[tuple[int, bytes]]) -> tuple[np.ndarray, np.ndarray]:
    """Convert (id, blob) rows into normalized vectors and an int64 id array."""
    vecs = np.array([blob_to_embedding(blob) for _, blob in batch], dtype=np.float32)
    ids = np.array([conv_id for conv_id, _ in batch], dtype=np.int64)
    faiss.normalize_L2(vecs)
    return vecs, ids


def _indexed_ids(index: faiss.Index) -> np.ndarray:
    """Return the convocatoria IDs stored in an IndexIDMap2."""
    return faiss.vector_to_array(index.id_map).astype(np.int64)


def _build_from_db(db_path: str | None) -> faiss.Index | None:
    """Build a new FAISS index from SQLite using the low-memory 2-pass strategy.

    Pass 1: Load a small sample to train the index (~300 MB peak).
    Pass 2: Stream all embeddings in batches to populate the trained index (~60 MB per batch).

    For >= 10K vectors: builds OPQ64,IVF1024,PQ64 (trained, ~40 MB for 600K).
    For < 10K vectors: builds IndexFlatIP (brute-force, fine at small scale).

    Does not touch the live index.

    Args:
        db_path: Override DB path (useful for tests).

    Returns:
        The populated index, or None if there are no embeddings.
    """
    # Lazy import to avoid circular dependency
    from backend.services.convocatorias_db import (
        get_embedding_count,
        iter_all_embeddings,
        sample_embeddings,
    )

    total = get_embedding_count(db_path=db_path)
    if total == 0:
        logger.warning("No embeddings found in DB — FAISS index not built")
        return None

    logger.info("Building FAISS index for %d embeddings (low-memory mode)...", total)

    if total < _IVF_THRESHOLD:
        # Small dataset — brute-force, load everything (small enough to fit in memory)
        logger.info("Building IndexFlatIP for %d vectors", total)
        id_index = faiss.IndexIDMap2(faiss.IndexFlatIP(EMBEDDING_DIMS))

        for batch in iter_all_embeddings(batch_size=_BATCH_SIZE, db_path=db_path):
            vecs, ids = _blobs_to_arrays(batch)
            id_index.add_with_ids(vecs, ids)
    else:
        # --- Pass 1: Train on a random sample (low memory) ---
        train_size = min(50_000, total)
        logger.info("Pass 1/2: Loading %d random vectors for training...", train_size)

        sample = sample_embeddings(train_size, db_path=db_path)
        train_data, _ = _blobs_to_arrays(sample)
        del sample  # Free blob data

        nlist = min(1024, total // 40)
        logger.info("Training OPQ64,IVF%d,PQ64 index on %d vectors...", nlist, train_size)
        index = faiss.index_factory(
            EMBEDDING_DIMS, f"OPQ64,IVF{nlist},PQ64", faiss.METRIC_INNER_PRODUCT
        )
        index.train(train_data)
        del train_data  # Free training data

        # --- Pass 2: Populate index in batches (low memory) ---
        id_index = faiss.IndexIDMap2(index)
        added = 0
        logger.info("Pass 2/2: Populating index in batches of %d...", _BATCH_SIZE)

        for batch in iter_all_embeddings(batch_size=_BATCH_SIZE, db_path=db_path):
            vecs, ids = _blobs_to_arrays(batch)
            id_index.add_with_ids(vecs, ids)
            added += len(batch)
            if added % 100_000 == 0:
                logger.info("  ... added %d / %d vectors", added, total)

    _configure(id_index)
    return id_index


def _add_to_index(index: faiss.Index, ids: np.ndarray, vecs: np.ndarray, live: bool) -> None:
    """Add vectors in chunks; take the search lock per chunk if the index is live."""
    for start in range(0, len(ids), _ADD_CHUNK_SIZE):
        chunk_ids = ids[start:start + _ADD_CHUNK_SIZE]
        chunk_vecs = vecs[start:start + _ADD_CHUNK_SIZE]
        if live:
            with _lock:
                index.add_with_ids(chunk_vecs, chunk_ids)
        else:
            index.add_with_ids(chunk_vecs, chunk_ids)


def _add_missing_from_db(index: faiss.Index, db_path: str | None, live: bool) -> int:
    """Add embeddings that are in SQLite but not in the index. Caller holds _write_lock.

    Args:
        index: Index to update.
        db_path: Override DB path (useful for tests).
        live: True if the index is serving searches (adds take the search lock).

    Returns:
        Number of vectors added.
    """
    from backend.services.convocatorias_db import get_embedding_ids, get_embeddings_by_ids

    db_ids = np.array(get_embedding_ids(db_path=db_path), dtype=np.int64)
    missing = np.setdiff1d(db_ids, _indexed_ids(index), assume_unique=True)
    if len(missing) == 0:
        return 0

    logger.info("Adding %d embeddings missing from FAISS index...", len(missing))
    added = 0
    missing_list = missing.tolist()
    for start in range(0, len(missing_list), _BATCH_SIZE):
        rows = get_embeddings_by_ids(missing_list[start:start + _BATCH_SIZE], db_path=db_path)
        if not rows:
            continue
        vecs, ids = _blobs_to_arrays(rows)
        _add_to_index(index, ids, vecs, live)
        added += len(rows)
    return added


def _save(index: faiss.Index, index_path: str) -> None:
    """Write index + metadata atomically (temp file + rename). Caller holds _write_lock."""
    Path(index_path).parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "format_version": _FORMAT_VERSION,
        "embedding_model": EMBEDDING_MODEL,
        "dims": EMBEDDING_DIMS,
        "total_vectors": int(index.ntotal),
        "built_at": _built_at,
        "saved_at": _now_iso(),
    }
    tmp_index = index_path + ".tmp"
    tmp_meta = _meta_path(index_path) + ".tmp"

    # No search lock needed: searches only read, and mutations hold _write_lock
    faiss.write_index(index, tmp_index)
    with open(tmp_meta, "w") as f:
        json.dump(meta, f)

    os.replace(tmp_index, index_path)
    os.replace(tmp_meta, _meta_path(index_path))
    logger.info("FAISS index saved to %s (%d vectors)", index_path, index.ntotal)


def _read_from_disk(index_path: str) -> tuple[faiss.Index, dict] | None:
    """Read a saved index if it exists and matches the current embedding setup.

    Returns:
        (index, metadata) or None if missing, incompatible or unreadable.
    """
    meta_path = _meta_path(index_path)
    if not (os.path.exists(index_path) and os.path.exists(meta_path)):
        logger.info("No saved FAISS index at %s", index_path)
        return None

    try:
        with open(meta_path) as f:
            meta = json.load(f)
        expected = {
            "format_version": _FORMAT_VERSION,
            "embedding_model": EMBEDDING_MODEL,
            "dims": EMBEDDING_DIMS,
        }
        mismatched = {k: meta.get(k) for k, v in expected.items() if meta.get(k) != v}
        if mismatched:
            logger.warning("Saved FAISS index is incompatible (%s) — rebuilding", mismatched)
            return None

        index = faiss.read_index(index_path)
        if not isinstance(index, faiss.IndexIDMap2) or index.d != EMBEDDING_DIMS:
            logger.warning("Saved FAISS index has unexpected type/dims — rebuilding")
            return None
    except Exception as e:
        logger.warning("Could not read saved FAISS index (%s) — rebuilding", e)
        return None

    _configure(index)
    return index, meta


def _swap(index: faiss.Index, built_at: str) -> None:
    """Make `index` the live index."""
    global _index, _ready, _built_at
    with _lock:
        _index = index
        _built_at = built_at
        _ready = True


def _rebuild_locked(db_path: str | None, index_path: str) -> None:
    """Full build + swap + save. Caller holds _write_lock."""
    index = _build_from_db(db_path)
    if index is None:
        return
    # Catch embeddings stored while we were building
    _add_missing_from_db(index, db_path, live=False)
    _swap(index, _now_iso())
    logger.info("FAISS index ready: %d vectors indexed", index.ntotal)
    _save(index, index_path)


def load_index_from_db(db_path: str | None = None, index_path: str | None = None) -> None:
    """Rebuild (retrain) the FAISS index from SQLite and save it to disk.

    Expensive (minutes and several GB of RAM for 600K+ vectors). The live index
    keeps serving searches until the new one is swapped in. Blocks while another
    build or update is running.

    Args:
        db_path: Override DB path (useful for tests).
        index_path: Override index file path (useful for tests).
    """
    with _write_lock:
        _rebuild_locked(db_path, _resolve_index_path(db_path, index_path))


def load_or_build(db_path: str | None = None, index_path: str | None = None) -> None:
    """Load the index from disk at startup, building it only if needed.

    After loading, embeddings added to SQLite since the last save are added
    incrementally (e.g. a sync that ran right before a restart).

    Args:
        db_path: Override DB path (useful for tests).
        index_path: Override index file path (useful for tests).
    """
    path = _resolve_index_path(db_path, index_path)
    with _write_lock:
        loaded = _read_from_disk(path)
        if loaded is None:
            _rebuild_locked(db_path, path)
            return

        index, meta = loaded
        _swap(index, meta.get("built_at") or _now_iso())
        logger.info(
            "FAISS index loaded from disk: %d vectors (built %s)",
            index.ntotal, meta.get("built_at"),
        )

        added = _add_missing_from_db(index, db_path, live=True)
        if added:
            logger.info("Added %d new vectors to FAISS index (total: %d)", added, index.ntotal)
            _save(index, path)


def sync_from_db(db_path: str | None = None, index_path: str | None = None) -> int:
    """Add embeddings that are in SQLite but not in the live index, then save.

    Called after syncs that generate embeddings. Cheap: no retraining. Waits if
    a build is in progress, then adds whatever that build didn't include.

    Args:
        db_path: Override DB path (useful for tests).
        index_path: Override index file path (useful for tests).

    Returns:
        Number of vectors added (0 if the index isn't loaded).
    """
    with _write_lock:
        if not _ready or _index is None:
            logger.warning("FAISS index not loaded — skipping incremental update")
            return 0

        added = _add_missing_from_db(_index, db_path, live=True)
        if added:
            logger.info("Added %d new vectors to FAISS index (total: %d)", added, _index.ntotal)
            _save(_index, _resolve_index_path(db_path, index_path))
        else:
            logger.info("FAISS index already up to date (%d vectors)", _index.ntotal)
        return added


def search(query_vec: np.ndarray, k: int = 500) -> list[tuple[int, float]]:
    """Search FAISS index for nearest neighbors.

    Args:
        query_vec: Query embedding (1D array of EMBEDDING_DIMS).
        k: Number of neighbors to return.

    Returns:
        List of (convocatoria_id, cosine_similarity) sorted by similarity desc.
        Returns [] if index not ready.
    """
    if not _ready or _index is None:
        return []

    # Reshape to (1, dims) and normalize
    qvec = query_vec.reshape(1, -1).astype(np.float32)
    faiss.normalize_L2(qvec)

    with _lock:
        # Limit k to total indexed vectors
        actual_k = min(k, _index.ntotal)
        if actual_k == 0:
            return []
        scores, ids = _index.search(qvec, actual_k)

    results = []
    for score, doc_id in zip(scores[0], ids[0]):
        if doc_id == -1:
            continue
        results.append((int(doc_id), float(score)))

    return results


def add_vectors(ids: list[int], vectors: np.ndarray) -> None:
    """Add new vectors to the live FAISS index (in memory only, not saved).

    Args:
        ids: List of convocatoria IDs.
        vectors: Array of shape (N, EMBEDDING_DIMS) with embeddings.
    """
    if not _ready or _index is None:
        logger.warning("Cannot add vectors — FAISS index not ready")
        return

    if len(ids) == 0:
        return

    vecs = vectors.astype(np.float32)
    faiss.normalize_L2(vecs)
    _add_to_index(_index, np.array(ids, dtype=np.int64), vecs, live=True)

    logger.info("Added %d vectors to FAISS index (total: %d)", len(ids), _index.ntotal)


def get_stats(index_path: str | None = None) -> dict:
    """Return FAISS index statistics.

    Returns:
        Dict with ready, total_vectors, index_type, building, built_at and
        whether the index file exists on disk.
    """
    path = index_path or FAISS_INDEX_PATH
    common = {
        "building": is_building(),
        "on_disk": os.path.exists(path),
        "index_path": path,
    }
    if not _ready or _index is None:
        return {"ready": False, "total_vectors": 0, "index_type": None, "built_at": None, **common}

    return {
        "ready": True,
        "total_vectors": _index.ntotal,
        "index_type": type(_index).__name__,
        "built_at": _built_at,
        **common,
    }


def reset() -> None:
    """Reset the index state. Used in tests."""
    global _index, _ready, _built_at
    with _lock:
        _index = None
        _ready = False
        _built_at = None
