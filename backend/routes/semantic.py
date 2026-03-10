"""Semantic search route — natural language grant search."""

from fastapi import APIRouter, Query

from backend.services.semantic_search import semantic_search

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
async def search(
    q: str = Query(default="", description="Natural language search query"),
    topK: int = Query(default=20, ge=1, le=50, description="Number of results"),
    region: str | None = Query(default=None, description="Region name filter"),
    yearFrom: int | None = Query(default=None, description="Start year"),
    yearTo: int | None = Query(default=None, description="End year"),
    abierto: bool | None = Query(default=None, description="Open status filter"),
) -> dict:
    """Search grants using natural language with semantic similarity.

    Returns results in the same format as /api/convocatorias for GrantCard compatibility.
    """
    filters = {}
    if abierto is not None:
        filters["abierto"] = abierto
    if yearFrom:
        filters["yearFrom"] = yearFrom
    if yearTo:
        filters["yearTo"] = yearTo

    return await semantic_search(
        query=q,
        filters=filters if filters else None,
        top_k=topK,
    )
