"""SEO routes: segmented dynamic sitemap (open/closed grants by year)."""

import logging
import math
import re
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import Response

from backend.config import SITE_BASE_URL
from backend.services.cache import TTLCache
from backend.services.convocatorias_db import (
    get_sitemap_closed_by_year,
    get_sitemap_closed_entries,
    get_sitemap_open_count,
    get_sitemap_open_entries,
    get_sitemap_open_max_updated,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_sitemap_cache = TTLCache(max_size=50)
_GRANTS_PER_SITEMAP = 50000

# Cache TTLs (seconds)
_TTL_INDEX = 3600  # 1h
_TTL_STATIC = 86400  # 24h
_TTL_OPEN = 3600  # 1h — grants can change status
_TTL_CLOSED_CURRENT_YEAR = 21600  # 6h — current year still receives closures
_TTL_CLOSED_PAST = 86400  # 24h — historical, stable

_STATIC_PAGES = [
    {"loc": "/", "changefreq": "daily", "priority": "1.0"},
    {"loc": "/buscar", "changefreq": "daily", "priority": "0.8"},
    {"loc": "/estadisticas", "changefreq": "weekly", "priority": "0.7"},
    {"loc": "/beneficiarios", "changefreq": "weekly", "priority": "0.7"},
    {"loc": "/contacto", "changefreq": "monthly", "priority": "0.3"},
]

# Regex for closed segment: "2025" or "2025-2"
_CLOSED_SEGMENT_RE = re.compile(r"^(\d{4})(?:-(\d+))?$")


def _xml_response(content: str, cache_max_age: int = 86400) -> Response:
    """Return an XML response with proper content type and cache header."""
    return Response(
        content=content,
        media_type="application/xml",
        headers={"Cache-Control": f"public, max-age={cache_max_age}"},
    )


def _build_urlset(entries: list[dict], changefreq: str, priority: str) -> str:
    """Build a <urlset> XML string from grant entries."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for entry in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{SITE_BASE_URL}/ayuda/{entry['numero']}</loc>")
        if entry.get("lastmod"):
            # Ensure date-only format (YYYY-MM-DD) for lastmod
            lastmod = entry["lastmod"][:10] if len(entry["lastmod"]) > 10 else entry["lastmod"]
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append(f"    <changefreq>{changefreq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines)


def _empty_urlset() -> str:
    """Return an empty <urlset> XML."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
    )


def invalidate_sitemap_cache() -> None:
    """Invalidate sitemap caches affected by sync.

    Clears: index, all open-* entries, closed-{current_year}.
    Leaves past-year closed caches untouched (they don't change).
    """
    current_year = str(datetime.now(timezone.utc).year)
    keys_to_remove = []
    for key in list(_sitemap_cache._store.keys()):
        if key == "sitemap-index":
            keys_to_remove.append(key)
        elif key.startswith("sitemap-grants-open"):
            keys_to_remove.append(key)
        elif key.startswith(f"sitemap-grants-closed-{current_year}"):
            keys_to_remove.append(key)
    for key in keys_to_remove:
        _sitemap_cache._store.pop(key, None)
    if keys_to_remove:
        logger.info("Invalidated %d sitemap cache entries after sync", len(keys_to_remove))


@router.get("/sitemap.xml")
async def sitemap_index() -> Response:
    """Sitemap index listing static + open batches + closed-by-year sitemaps."""
    cached = _sitemap_cache.get("sitemap-index")
    if cached:
        return _xml_response(cached, cache_max_age=_TTL_INDEX)

    open_count = get_sitemap_open_count()
    open_max_updated = get_sitemap_open_max_updated()
    closed_years = get_sitemap_closed_by_year()

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f"  <sitemap>",
        f"    <loc>{SITE_BASE_URL}/sitemap-static.xml</loc>",
        f"    <lastmod>{now_iso}</lastmod>",
        f"  </sitemap>",
    ]

    # Open grant sitemaps
    num_open_pages = max(1, math.ceil(open_count / _GRANTS_PER_SITEMAP))
    open_lastmod = open_max_updated[:10] if open_max_updated else now_iso
    for i in range(1, num_open_pages + 1):
        lines.append(f"  <sitemap>")
        lines.append(f"    <loc>{SITE_BASE_URL}/sitemap-grants-open-{i}.xml</loc>")
        lines.append(f"    <lastmod>{open_lastmod}</lastmod>")
        lines.append(f"  </sitemap>")

    # Closed grant sitemaps by year
    for year_info in closed_years:
        year = year_info["year"]
        count = year_info["count"]
        last_mod = year_info["last_modified"]
        year_lastmod = last_mod[:10] if last_mod else now_iso
        num_pages = math.ceil(count / _GRANTS_PER_SITEMAP)

        if num_pages <= 1:
            lines.append(f"  <sitemap>")
            lines.append(f"    <loc>{SITE_BASE_URL}/sitemap-grants-closed-{year}.xml</loc>")
            lines.append(f"    <lastmod>{year_lastmod}</lastmod>")
            lines.append(f"  </sitemap>")
        else:
            for p in range(1, num_pages + 1):
                suffix = f"{year}" if p == 1 else f"{year}-{p}"
                lines.append(f"  <sitemap>")
                lines.append(f"    <loc>{SITE_BASE_URL}/sitemap-grants-closed-{suffix}.xml</loc>")
                lines.append(f"    <lastmod>{year_lastmod}</lastmod>")
                lines.append(f"  </sitemap>")

    lines.append("</sitemapindex>")

    xml = "\n".join(lines)
    _sitemap_cache.set("sitemap-index", xml, _TTL_INDEX)
    logger.info(
        "Generated sitemap index: %d open pages, %d closed year groups, %d total grants",
        num_open_pages,
        len(closed_years),
        open_count + sum(y["count"] for y in closed_years),
    )
    return _xml_response(xml, cache_max_age=_TTL_INDEX)


@router.get("/sitemap-static.xml")
async def sitemap_static() -> Response:
    """Sitemap for static pages."""
    cached = _sitemap_cache.get("sitemap-static")
    if cached:
        return _xml_response(cached, cache_max_age=_TTL_STATIC)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for page in _STATIC_PAGES:
        lines.append("  <url>")
        lines.append(f"    <loc>{SITE_BASE_URL}{page['loc']}</loc>")
        lines.append(f"    <changefreq>{page['changefreq']}</changefreq>")
        lines.append(f"    <priority>{page['priority']}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")

    xml = "\n".join(lines)
    _sitemap_cache.set("sitemap-static", xml, _TTL_STATIC)
    return _xml_response(xml, cache_max_age=_TTL_STATIC)


@router.get("/sitemap-grants-open-{page}.xml")
async def sitemap_grants_open(page: int) -> Response:
    """Paginated sitemap for open grant detail pages.

    Args:
        page: 1-indexed page number.
    """
    if page < 1:
        return _xml_response(_empty_urlset())

    cache_key = f"sitemap-grants-open-{page}"
    cached = _sitemap_cache.get(cache_key)
    if cached:
        return _xml_response(cached, cache_max_age=_TTL_OPEN)

    entries = get_sitemap_open_entries(page - 1, _GRANTS_PER_SITEMAP)
    xml = _build_urlset(entries, changefreq="weekly", priority="0.8")
    _sitemap_cache.set(cache_key, xml, _TTL_OPEN)
    return _xml_response(xml, cache_max_age=_TTL_OPEN)


@router.get("/sitemap-grants-closed-{segment}.xml")
async def sitemap_grants_closed(segment: str) -> Response:
    """Sitemap for closed grants of a specific year (with optional overflow page).

    Segment format: "2025" (page 1) or "2025-2" (page 2 of year 2025).
    """
    match = _CLOSED_SEGMENT_RE.match(segment)
    if not match:
        return _xml_response(_empty_urlset())

    year = match.group(1)
    page = int(match.group(2)) if match.group(2) else 1
    if page < 1:
        return _xml_response(_empty_urlset())

    cache_key = f"sitemap-grants-closed-{segment}"
    cached = _sitemap_cache.get(cache_key)
    if cached:
        current_year = str(datetime.now(timezone.utc).year)
        ttl = _TTL_CLOSED_CURRENT_YEAR if year == current_year else _TTL_CLOSED_PAST
        return _xml_response(cached, cache_max_age=ttl)

    entries = get_sitemap_closed_entries(year, page - 1, _GRANTS_PER_SITEMAP)

    current_year = str(datetime.now(timezone.utc).year)
    is_current = year == current_year
    changefreq = "monthly" if is_current else "yearly"
    priority = "0.4" if is_current else "0.3"
    ttl = _TTL_CLOSED_CURRENT_YEAR if is_current else _TTL_CLOSED_PAST

    xml = _build_urlset(entries, changefreq=changefreq, priority=priority)
    _sitemap_cache.set(cache_key, xml, ttl)
    return _xml_response(xml, cache_max_age=ttl)
