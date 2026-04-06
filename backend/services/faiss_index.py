"""FAISS in-memory vector index for semantic search over all convocatorias."""

import logging
import threading

import faiss
import numpy as np

from backend.services.embeddings import EMBEDDING_DIMS, blob_to_embedding

logger = logging.getLogger(__name__)

# Global index state
_index: faiss.Index | None = None
_id_array: np.ndarray | None = None  # Maps FAISS sequential position -> convocatoria.id
_ready: bool = False
_lock = threading.Lock()

# Minimum vectors to justify training an IVF index
_IVF_THRESHOLD = 10_000
_BATCH_SIZE = 10_000


def is_ready() -> bool:
    """Check if FAISS index is loaded and ready for queries."""
    return _ready


def load_index_from_db(db_path: str | None = None) -> None:
    """Load embeddings from SQLite and build FAISS index using low-memory 2-pass strategy.

    Pass 1: Load a small sample to train the index (~300 MB peak).
    Pass 2: Stream all embeddings in batches to populate the trained index (~60 MB per batch).

    For >= 10K vectors: builds OPQ64,IVF1024,PQ64 (trained, ~40 MB for 600K).
    For < 10K vectors: builds IndexFlatIP (brute-force, fine at small scale).

    Args:
        db_path: Override DB path (useful for tests).
    """
    global _index, _id_array, _ready

    # Lazy import to avoid circular dependency
    from backend.services.convocatorias_db import (
        get_embedding_count,
        iter_all_embeddings,
        sample_embeddings,
    )

    total = get_embedding_count(db_path=db_path)
    if total == 0:
        logger.warning("No embeddings found in DB — FAISS index not built")
        return

    logger.info("Building FAISS index for %d embeddings (low-memory mode)...", total)

    if total < _IVF_THRESHOLD:
        # Small dataset — brute-force, load everything (small enough to fit in memory)
        logger.info("Building IndexFlatIP for %d vectors", total)
        index = faiss.IndexFlatIP(EMBEDDING_DIMS)
        id_index = faiss.IndexIDMap2(index)

        for batch in iter_all_embeddings(batch_size=_BATCH_SIZE, db_path=db_path):
            batch_vecs = np.array(
                [blob_to_embedding(blob) for _, blob in batch], dtype=np.float32
            )
            batch_ids = np.array([conv_id for conv_id, _ in batch], dtype=np.int64)
            faiss.normalize_L2(batch_vecs)
            id_index.add_with_ids(batch_vecs, batch_ids)
    else:
        # --- Pass 1: Train on a random sample (low memory) ---
        train_size = min(50_000, total)
        logger.info("Pass 1/2: Loading %d random vectors for training...", train_size)

        sample = sample_embeddings(train_size, db_path=db_path)
        train_data = np.array(
            [blob_to_embedding(blob) for _, blob in sample], dtype=np.float32
        )
        del sample  # Free blob data
        faiss.normalize_L2(train_data)

        nlist = min(1024, total // 40)
        logger.info("Training OPQ64,IVF%d,PQ64 index on %d vectors...", nlist, train_size)
        index = faiss.index_factory(
            EMBEDDING_DIMS, f"OPQ64,IVF{nlist},PQ64", faiss.METRIC_INNER_PRODUCT
        )
        index.train(train_data)
        del train_data  # Free training data

        ivf = faiss.extract_index_ivf(index)
        ivf.nprobe = 32

        # --- Pass 2: Populate index in batches (low memory) ---
        id_index = faiss.IndexIDMap2(index)
        added = 0
        logger.info("Pass 2/2: Populating index in batches of %d...", _BATCH_SIZE)

        for batch in iter_all_embeddings(batch_size=_BATCH_SIZE, db_path=db_path):
            batch_vecs = np.array(
                [blob_to_embedding(blob) for _, blob in batch], dtype=np.float32
            )
            batch_ids = np.array([conv_id for conv_id, _ in batch], dtype=np.int64)
            faiss.normalize_L2(batch_vecs)
            id_index.add_with_ids(batch_vecs, batch_ids)
            added += len(batch)
            if added % 100_000 == 0:
                logger.info("  ... added %d / %d vectors", added, total)

    all_ids = np.array(faiss.vector_to_array(id_index.id_map), dtype=np.int64)

    with _lock:
        _index = id_index
        _id_array = all_ids
        _ready = True

    logger.info("FAISS index ready: %d vectors indexed", id_index.ntotal)


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
    """Add new vectors to the FAISS index incrementally.

    Args:
        ids: List of convocatoria IDs.
        vectors: Array of shape (N, EMBEDDING_DIMS) with embeddings.
    """
    global _id_array

    if not _ready or _index is None:
        logger.warning("Cannot add vectors — FAISS index not ready")
        return

    if len(ids) == 0:
        return

    vecs = vectors.astype(np.float32)
    faiss.normalize_L2(vecs)
    id_arr = np.array(ids, dtype=np.int64)

    with _lock:
        _index.add_with_ids(vecs, id_arr)
        _id_array = np.concatenate([_id_array, id_arr]) if _id_array is not None else id_arr

    logger.info("Added %d vectors to FAISS index (total: %d)", len(ids), _index.ntotal)


def get_stats() -> dict:
    """Return FAISS index statistics.

    Returns:
        Dict with ready, total_vectors, index_type.
    """
    if not _ready or _index is None:
        return {"ready": False, "total_vectors": 0, "index_type": None}

    return {
        "ready": True,
        "total_vectors": _index.ntotal,
        "index_type": type(_index).__name__,
    }


def reset() -> None:
    """Reset the index state. Used in tests."""
    global _index, _id_array, _ready
    with _lock:
        _index = None
        _id_array = None
        _ready = False
