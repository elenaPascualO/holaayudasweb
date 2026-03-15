"""Hybrid semantic search: FTS5 pre-filter + cosine similarity re-ranking."""

import logging

import numpy as np

from backend.services.convocatorias_db import (
    _row_to_search_result,
    aggregate_by_year_for_ids,
    get_recent_with_embeddings,
    search_fts,
)
from backend.services.embeddings import (
    blob_to_embedding,
    generate_embeddings_batch,
)

logger = logging.getLogger(__name__)


def _cosine_similarity_batch(
    query_vec: np.ndarray, candidate_vecs: np.ndarray
) -> np.ndarray:
    """Compute cosine similarity between a query vector and candidate vectors.

    Args:
        query_vec: 1D array (1536,).
        candidate_vecs: 2D array (N, 1536).

    Returns:
        1D array of similarity scores (N,).
    """
    # Normalize
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    norms = np.linalg.norm(candidate_vecs, axis=1, keepdims=True) + 1e-10
    candidate_norms = candidate_vecs / norms
    return candidate_norms @ query_norm


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


async def semantic_search(
    query: str,
    filters: dict | None = None,
    top_k: int = 20,
    fts_candidates: int = 500,
) -> dict:
    """Perform hybrid semantic search.

    1. FTS5 pre-filters candidates by text match
    2. OpenAI embeds the query
    3. Cosine similarity re-ranks candidates
    4. Filters (status, year) applied AFTER ranking to preserve relevance
    5. Returns top_k results in BDNS-compatible format

    Args:
        query: User search text in natural language.
        filters: Optional dict with keys: abierto, yearFrom, yearTo.
        top_k: Number of results to return.
        fts_candidates: Max candidates from FTS5 pre-filter.

    Returns:
        Paginated response in BDNS format.
    """
    if not query.strip():
        return {
            "content": [],
            "totalElements": 0,
            "totalPages": 0,
            "number": 0,
            "size": top_k,
        }

    # Step 1: FTS5 pre-filter (no status/year filters — applied after ranking)
    candidates = search_fts(query, limit=fts_candidates)

    # Step 2: If too few FTS results, fall back to recent embeddings
    if len(candidates) < top_k:
        logger.info(
            "FTS returned %d candidates (< %d), adding recent embeddings",
            len(candidates), top_k,
        )
        recent = get_recent_with_embeddings(limit=5000)

        # Merge: FTS candidates first, then recent (dedup by id)
        seen_ids = {c["id"] for c in candidates}
        for r in recent:
            if r["id"] not in seen_ids:
                candidates.append(r)
                seen_ids.add(r["id"])

    # Filter to only candidates with embeddings
    candidates_with_emb = [c for c in candidates if c.get("embedding")]

    if not candidates_with_emb:
        # No embeddings available — return FTS results as-is, filtered by date
        logger.info("No embeddings available, returning FTS results by date")
        results = _apply_filters(candidates, filters)[:top_k]
        return _build_response(results, top_k)

    # Step 3: Embed the query
    try:
        query_embeddings = await generate_embeddings_batch([query])
        query_vec = np.array(query_embeddings[0], dtype=np.float32)
    except Exception as e:
        logger.error("Failed to embed query: %s", e)
        # Fallback: return FTS results by date, filtered
        results = _apply_filters(candidates, filters)[:top_k]
        return _build_response(results, top_k)

    # Step 4: Compute cosine similarity
    candidate_vecs = np.array(
        [blob_to_embedding(c["embedding"]) for c in candidates_with_emb],
        dtype=np.float32,
    )
    scores = _cosine_similarity_batch(query_vec, candidate_vecs)

    # Step 5: Sort by score
    scored = list(zip(candidates_with_emb, scores.tolist()))
    scored.sort(key=lambda x: x[1], reverse=True)

    # Step 6: Apply filters AFTER ranking to preserve semantic relevance
    if filters:
        scored = [(c, s) for c, s in scored if _passes_filters(c, filters)]
    top_results = scored[:top_k]

    return _build_scored_response(top_results, top_k)


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
) -> dict:
    """Aggregate matching convocatorias by year for trend analysis.

    Hybrid pipeline (FTS5 + embeddings) similar to semantic_search(),
    but collects ALL matching IDs and aggregates by year instead of
    returning paginated results.

    Args:
        query: User search text.
        similarity_threshold: Min cosine similarity for embedding matches.
        fts_limit: Max candidates from FTS5 pre-filter.

    Returns:
        Dict with query, total_matches, by_year: [{year, count, budget}].
    """
    if not query or not query.strip():
        return {"query": query, "total_matches": 0, "by_year": []}

    # Step 1: FTS5 pre-filter with high limit
    fts_candidates = search_fts(query, limit=fts_limit)
    fts_ids = {c["id"] for c in fts_candidates}

    # Step 2: Supplement with recent embeddings if few FTS hits
    all_candidates = list(fts_candidates)
    if len(fts_candidates) < fts_limit:
        recent = get_recent_with_embeddings(limit=fts_limit)
        seen_ids = set(fts_ids)
        for r in recent:
            if r["id"] not in seen_ids:
                all_candidates.append(r)
                seen_ids.add(r["id"])

    # Step 3: Embed query and compute cosine similarity
    embedding_ids: set[int] = set()
    candidates_with_emb = [c for c in all_candidates if c.get("embedding")]

    if candidates_with_emb:
        try:
            query_embeddings = await generate_embeddings_batch([query])
            query_vec = np.array(query_embeddings[0], dtype=np.float32)

            candidate_vecs = np.array(
                [blob_to_embedding(c["embedding"]) for c in candidates_with_emb],
                dtype=np.float32,
            )
            scores = _cosine_similarity_batch(query_vec, candidate_vecs)

            for candidate, score in zip(candidates_with_emb, scores.tolist()):
                if score >= similarity_threshold:
                    embedding_ids.add(candidate["id"])
        except Exception as e:
            logger.error("Keyword trend embedding failed: %s", e)
            # Fall through — use FTS IDs only

    # Step 4: Union of FTS matches + embedding matches
    matched_ids = list(fts_ids | embedding_ids)

    if not matched_ids:
        return {"query": query, "total_matches": 0, "by_year": []}

    # Step 5: Aggregate by year
    by_year = aggregate_by_year_for_ids(matched_ids)

    return {
        "query": query,
        "total_matches": len(matched_ids),
        "by_year": by_year,
    }
