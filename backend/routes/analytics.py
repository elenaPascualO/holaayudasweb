"""Analytics routes — grant data insights for journalists and analysts."""

from fastapi import APIRouter, Query

from backend.services.cache import cache
from backend.services.convocatorias_db import (
    analytics_by_region,
    analytics_by_theme,
    analytics_by_year,
    analytics_monthly_trend,
    analytics_status,
    analytics_summary,
    analytics_top_organs,
)
from backend.services.semantic_search import keyword_trend

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

CACHE_TTL = 3600  # 1 hour
KEYWORD_TREND_TTL = 600  # 10 minutes


@router.get("/summary")
async def summary() -> dict:
    """Get general summary statistics."""
    key = "analytics:summary"
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = analytics_summary()
    cache.set(key, data, CACHE_TTL)
    return data


@router.get("/by-year")
async def by_year() -> list[dict]:
    """Get convocatorias count and budget by year."""
    key = "analytics:by-year"
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = analytics_by_year()
    cache.set(key, data, CACHE_TTL)
    return data


@router.get("/monthly-trend")
async def monthly_trend(
    year: int = Query(description="Year to show monthly trend"),
) -> list[dict]:
    """Get monthly trend for a specific year."""
    key = f"analytics:monthly:{year}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = analytics_monthly_trend(year)
    cache.set(key, data, CACHE_TTL)
    return data


@router.get("/by-theme")
async def by_theme(
    yearFrom: int | None = Query(default=None, description="Start year filter"),
    yearTo: int | None = Query(default=None, description="End year filter"),
    limit: int = Query(default=15, ge=1, le=50, description="Max results"),
) -> list[dict]:
    """Get convocatorias by theme/finalidad."""
    key = f"analytics:theme:{yearFrom}:{yearTo}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = analytics_by_theme(yearFrom, yearTo, limit)
    cache.set(key, data, CACHE_TTL)
    return data


@router.get("/by-region")
async def by_region(
    yearFrom: int | None = Query(default=None, description="Start year filter"),
    yearTo: int | None = Query(default=None, description="End year filter"),
    limit: int = Query(default=20, ge=1, le=50, description="Max results"),
) -> list[dict]:
    """Get convocatorias by region."""
    key = f"analytics:region:{yearFrom}:{yearTo}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = analytics_by_region(yearFrom, yearTo, limit)
    cache.set(key, data, CACHE_TTL)
    return data


@router.get("/top-organs")
async def top_organs(
    yearFrom: int | None = Query(default=None, description="Start year filter"),
    yearTo: int | None = Query(default=None, description="End year filter"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
) -> list[dict]:
    """Get top convocante organisms by number of grants."""
    key = f"analytics:organs:{yearFrom}:{yearTo}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = analytics_top_organs(yearFrom, yearTo, limit)
    cache.set(key, data, CACHE_TTL)
    return data


@router.get("/status")
async def status() -> dict:
    """Get open vs closed grant counts."""
    key = "analytics:status"
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = analytics_status()
    cache.set(key, data, CACHE_TTL)
    return data


@router.get("/keyword-trend")
async def keyword_trend_endpoint(
    q: str = Query(description="Keyword to analyze"),
) -> dict:
    """Get year-by-year trend for a keyword using semantic search."""
    normalized = q.strip().lower()
    key = f"analytics:keyword-trend:{normalized}"
    cached_data = cache.get(key)
    if cached_data is not None:
        return cached_data
    data = await keyword_trend(q)
    cache.set(key, data, KEYWORD_TREND_TTL)
    return data
