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
    """Load all embeddings from SQLite and build FAISS index.

    For >= 10K vectors: builds OPQ64,IVF1024,PQ64 (trained, ~40 MB for 600K).
    For < 10K vectors: builds IndexFlatIP (brute-force, fine at small scale).

    Args:
        db_path: Override DB path (useful for tests).
    """
    global _index, _id_array, _ready

    # Lazy import to avoid circular dependency
    from backend.services.convocatorias_db import get_embedding_count, iter_all_embeddings

    total = get_embedding_count(db_path=db_path)
    if total == 0:
        logger.warning("No embeddings found in DB — FAISS index not built")
        return

    logger.info("Loading %d embeddings from SQLite for FAISS index...", total)

    # Read all embeddings in batches
    all_ids: list[int] = []
    all_vecs: list[np.ndarray] = []

    for batch in iter_all_embeddings(batch_size=_BATCH_SIZE, db_path=db_path):
        batch_ids = []
        batch_vecs = []
        for conv_id, blob in batch:
            batch_ids.append(conv_id)
            batch_vecs.append(blob_to_embedding(blob))
        all_ids.extend(batch_ids)
        all_vecs.append(np.array(batch_vecs, dtype=np.float32))

    ids = np.array(all_ids, dtype=np.int64)
    vectors = np.vstack(all_vecs)

    # Normalize vectors (OpenAI embeddings should already be normalized, but be safe)
    faiss.normalize_L2(vectors)

    if total < _IVF_THRESHOLD:
        # Small dataset — brute-force is fine
        logger.info("Building IndexFlatIP for %d vectors", total)
        index = faiss.IndexFlatIP(EMBEDDING_DIMS)
    else:
        # Large dataset — use OPQ + IVF + PQ for memory efficiency
        nlist = min(1024, total // 40)  # ~40 vectors per cluster minimum
        logger.info(
            "Building OPQ64,IVF%d,PQ64 index for %d vectors...", nlist, total
        )
        index = faiss.index_factory(EMBEDDING_DIMS, f"OPQ64,IVF{nlist},PQ64", faiss.METRIC_INNER_PRODUCT)

        # Train on a sample (up to 50K random vectors)
        train_size = min(50_000, total)
        if train_size < total:
            sample_idx = np.random.choice(total, train_size, replace=False)
            train_data = vectors[sample_idx]
        else:
            train_data = vectors

        logger.info("Training FAISS index on %d vectors...", train_size)
        index.train(train_data)

        # Set nprobe for search quality
        ivf = faiss.extract_index_ivf(index)
        ivf.nprobe = 32

    # Wrap with IDMap2 to map FAISS positions to convocatoria IDs
    id_index = faiss.IndexIDMap2(index)
    id_index.add_with_ids(vectors, ids)

    with _lock:
        _index = id_index
        _id_array = ids
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
