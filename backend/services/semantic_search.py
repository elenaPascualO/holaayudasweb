"""Hybrid search: FTS5 keyword search + FAISS vector search + RRF fusion."""

import logging

import numpy as np

import backend.services.faiss_index as faiss_index
from backend.services.beneficiarios_db import (
    has_data as has_beneficiarios_data,
    search_beneficiarios_trend,
)
from backend.services.convocatorias_db import (
    _row_to_search_result,
    aggregate_by_year_for_ids,
    get_convocatorias_by_ids,
    search_fts,
)
from backend.services.embeddings import generate_embeddings_batch

logger = logging.getLogger(__name__)


def _passes_filters(candidate: dict, filters: dict) -> bool:
    """Check if a single candidate passes all filters.

    Args:
        candidate: Convocatoria dict.
        filters: Dict with keys: abierto, yearFrom, yearTo.

    Returns:
        True if candidate passes all filters.
    """
    if filters.get("abierto") is not None:
        abierto_val = 1 if filters["abierto"] else 0
        if candidate.get("abierto") != abierto_val:
            return False

    if filters.get("yearFrom"):
        if candidate.get("fecha_recepcion", "") < f"{filters['yearFrom']}-01-01":
            return False

    if filters.get("yearTo"):
        if candidate.get("fecha_recepcion", "") > f"{filters['yearTo']}-12-31":
            return False

    return True


def _apply_filters(candidates: list[dict], filters: dict | None) -> list[dict]:
    """Apply optional filters to candidate results.

    Args:
        candidates: List of convocatoria dicts.
        filters: Optional dict with keys: abierto, yearFrom, yearTo.

    Returns:
        Filtered list.
    """
    if not filters:
        return candidates
    return [c for c in candidates if _passes_filters(c, filters)]


def reciprocal_rank_fusion(
    ranked_lists: list[list[int]], k: int = 60
) -> list[tuple[int, float]]:
    """Combine multiple ranked lists using Reciprocal Rank Fusion.

    Each document's score = sum(1 / (k + rank)) across all lists it appears in.
    Documents appearing in multiple lists get boosted.

    Args:
        ranked_lists: List of lists, each containing doc IDs in ranked order.
        k: Smoothing constant (default 60, from original RRF paper).

    Returns:
        List of (doc_id, rrf_score) sorted by score descending.
    """
    scores: dict[int, float] = {}
    for ranked_list in ranked_lists:
        for rank, doc_id in enumerate(ranked_list, start=1):
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


async def _embed_query(query: str) -> np.ndarray | None:
    """Embed a query string via OpenAI. Returns None on failure."""
    try:
        embeddings = await generate_embeddings_batch([query])
        return np.array(embeddings[0], dtype=np.float32)
    except Exception as e:
        logger.error("Failed to embed query: %s", e)
        return None


async def semantic_search(
    query: str,
    filters: dict | None = None,
    top_k: int = 20,
    fts_candidates: int = 500,
    faiss_candidates: int = 500,
    rrf_k: int = 60,
    similarity_threshold: float = 0.25,
) -> dict:
    """Perform hybrid search using FTS5 + FAISS + RRF fusion.

    1. FTS5 retrieves keyword matches (ranked by BM25)
    2. FAISS retrieves semantic matches from full corpus (ranked by cosine similarity)
    3. RRF merges both ranked lists — docs in both lists rank highest
    4. Filters (status, year) applied AFTER ranking
    5. Returns top_k results in BDNS-compatible format

    Args:
        query: User search text in natural language.
        filters: Optional dict with keys: abierto, yearFrom, yearTo.
        top_k: Number of results to return.
        fts_candidates: Max candidates from FTS5.
        faiss_candidates: Max candidates from FAISS.
        rrf_k: RRF smoothing constant (default 60).
        similarity_threshold: Minimum cosine similarity for FAISS results.

    Returns:
        Paginated response in BDNS format.
    """
    if not query.strip():
        return _empty_response(top_k)

    # Step 1: FTS5 keyword search
    fts_results = search_fts(query, limit=fts_candidates)
    fts_ranked_ids = [r["id"] for r in fts_results]
    fts_by_id = {r["id"]: r for r in fts_results}

    # Step 2: FAISS vector search (if index is ready)
    faiss_ranked_ids: list[int] = []
    if faiss_index.is_ready():
        query_vec = await _embed_query(query)
        if query_vec is not None:
            faiss_hits = faiss_index.search(query_vec, k=faiss_candidates)
            faiss_ranked_ids = [
                doc_id for doc_id, score in faiss_hits
                if score >= similarity_threshold
            ]

    # Step 3: RRF fusion
    ranked_lists = []
    if fts_ranked_ids:
        ranked_lists.append(fts_ranked_ids)
    if faiss_ranked_ids:
        ranked_lists.append(faiss_ranked_ids)

    if not ranked_lists:
        return _empty_response(top_k)

    fused = reciprocal_rank_fusion(ranked_lists, k=rrf_k)

    # Step 4: Hydrate metadata for all results
    # FAISS-only results need metadata from SQLite
    faiss_only_ids = [
        doc_id for doc_id, _ in fused
        if doc_id not in fts_by_id
    ]
    if faiss_only_ids:
        extra = get_convocatorias_by_ids(faiss_only_ids)
        fts_by_id.update(extra)

    # Step 5: Build result list with RRF scores
    scored_results: list[tuple[dict, float]] = []
    for doc_id, rrf_score in fused:
        candidate = fts_by_id.get(doc_id)
        if candidate is None:
            continue
        scored_results.append((candidate, rrf_score))

    # Step 6: Apply filters AFTER ranking
    if filters:
        scored_results = [
            (c, s) for c, s in scored_results if _passes_filters(c, filters)
        ]

    top_results = scored_results[:top_k]
    return _build_scored_response(top_results, top_k)


def _empty_response(top_k: int) -> dict:
    """Return an empty BDNS-compatible response."""
    return {
        "content": [],
        "totalElements": 0,
        "totalPages": 0,
        "number": 0,
        "size": top_k,
    }


def _build_response(candidates: list[dict], top_k: int) -> dict:
    """Build BDNS-compatible response from candidate dicts (no scores).

    Args:
        candidates: List of convocatoria dicts from SQLite.
        top_k: Page size.

    Returns:
        Paginated response.
    """
    content = [_row_to_search_result(c) for c in candidates]
    return {
        "content": content,
        "totalElements": len(content),
        "totalPages": 1,
        "number": 0,
        "size": top_k,
    }


def _build_scored_response(
    scored_results: list[tuple[dict, float]], top_k: int
) -> dict:
    """Build BDNS-compatible response with relevance scores.

    Args:
        scored_results: List of (candidate_dict, score) tuples.
        top_k: Page size.

    Returns:
        Paginated response with _score field.
    """
    content = []
    for candidate, score in scored_results:
        result = _row_to_search_result(candidate)
        result["_score"] = round(score, 4)
        content.append(result)

    return {
        "content": content,
        "totalElements": len(content),
        "totalPages": 1,
        "number": 0,
        "size": top_k,
    }


async def keyword_trend(
    query: str,
    similarity_threshold: float = 0.3,
    fts_limit: int = 5000,
    faiss_limit: int = 5000,
) -> dict:
    """Aggregate matching convocatorias by year for trend analysis.

    Hybrid pipeline: FTS5 keyword matches + FAISS semantic matches,
    unioned, then aggregated by year.

    Args:
        query: User search text.
        similarity_threshold: Min cosine similarity for FAISS matches.
        fts_limit: Max candidates from FTS5.
        faiss_limit: Max candidates from FAISS.

    Returns:
        Dict with query, total_matches, by_year: [{year, count, budget}].
    """
    if not query or not query.strip():
        return {
            "query": query,
            "total_matches": 0,
            "by_year": [],
            "beneficiarios": None,
        }

    # Step 1: FTS5 keyword matches
    fts_candidates = search_fts(query, limit=fts_limit)
    fts_ids = {c["id"] for c in fts_candidates}

    # Step 2: FAISS semantic matches (if ready)
    faiss_ids: set[int] = set()
    if faiss_index.is_ready():
        query_vec = await _embed_query(query)
        if query_vec is not None:
            faiss_hits = faiss_index.search(query_vec, k=faiss_limit)
            faiss_ids = {
                doc_id for doc_id, score in faiss_hits
                if score >= similarity_threshold
            }

    # Step 3: Union of both sources
    matched_ids = list(fts_ids | faiss_ids)

    # Step 4: Aggregate by year
    by_year = aggregate_by_year_for_ids(matched_ids) if matched_ids else []

    # Step 5: Search beneficiarios
    beneficiarios_result = None
    try:
        if has_beneficiarios_data():
            benef_data = search_beneficiarios_trend(query)
            if benef_data["total_matches"] > 0:
                beneficiarios_result = benef_data
    except Exception as e:
        logger.error("Beneficiarios trend search failed: %s", e)

    return {
        "query": query,
        "total_matches": len(matched_ids),
        "by_year": by_year,
        "beneficiarios": beneficiarios_result,
    }
