"""SEO routes: dynamic sitemap index and paginated grant sitemaps."""

import math

from fastapi import APIRouter
from fastapi.responses import Response

from backend.services.cache import TTLCache
from backend.services.convocatorias_db import (
    get_sitemap_entries_page,
    get_sitemap_total_count,
)

router = APIRouter()

_sitemap_cache = TTLCache(max_size=20)
_SITEMAP_TTL = 86400  # 24 hours
_GRANTS_PER_SITEMAP = 50000
_BASE_URL = "https://www.holaayudas.com"

_STATIC_PAGES = [
    {"loc": "/", "changefreq": "daily", "priority": "1.0"},
    {"loc": "/buscar", "changefreq": "daily", "priority": "0.8"},
    {"loc": "/datos", "changefreq": "weekly", "priority": "0.7"},
    {"loc": "/transparencia", "changefreq": "weekly", "priority": "0.7"},
    {"loc": "/contacto", "changefreq": "monthly", "priority": "0.3"},
]


def _xml_response(content: str) -> Response:
    """Return an XML response with proper content type."""
    return Response(
        content=content,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/sitemap.xml")
async def sitemap_index() -> Response:
    """Sitemap index listing static + paginated grant sitemaps."""
    cached = _sitemap_cache.get("sitemap-index")
    if cached:
        return _xml_response(cached)

    total = get_sitemap_total_count()
    num_grant_pages = max(1, math.ceil(total / _GRANTS_PER_SITEMAP))

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f"  <sitemap><loc>{_BASE_URL}/sitemap-static.xml</loc></sitemap>",
    ]
    for i in range(1, num_grant_pages + 1):
        lines.append(f"  <sitemap><loc>{_BASE_URL}/sitemap-grants-{i}.xml</loc></sitemap>")
    lines.append("</sitemapindex>")

    xml = "\n".join(lines)
    _sitemap_cache.set("sitemap-index", xml, _SITEMAP_TTL)
    return _xml_response(xml)


@router.get("/sitemap-static.xml")
async def sitemap_static() -> Response:
    """Sitemap for static pages."""
    cached = _sitemap_cache.get("sitemap-static")
    if cached:
        return _xml_response(cached)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for page in _STATIC_PAGES:
        lines.append("  <url>")
        lines.append(f"    <loc>{_BASE_URL}{page['loc']}</loc>")
        lines.append(f"    <changefreq>{page['changefreq']}</changefreq>")
        lines.append(f"    <priority>{page['priority']}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")

    xml = "\n".join(lines)
    _sitemap_cache.set("sitemap-static", xml, _SITEMAP_TTL)
    return _xml_response(xml)


@router.get("/sitemap-grants-{page}.xml")
async def sitemap_grants(page: int) -> Response:
    """Paginated sitemap for open grant detail pages.

    Args:
        page: 1-indexed page number.
    """
    if page < 1:
        return _xml_response(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        )

    cache_key = f"sitemap-grants-{page}"
    cached = _sitemap_cache.get(cache_key)
    if cached:
        return _xml_response(cached)

    # Convert 1-indexed page to 0-indexed for DB query
    entries = get_sitemap_entries_page(page - 1, _GRANTS_PER_SITEMAP)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for entry in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{_BASE_URL}/ayuda/{entry['numero']}</loc>")
        if entry.get("fecha"):
            lines.append(f"    <lastmod>{entry['fecha']}</lastmod>")
        lines.append("    <changefreq>weekly</changefreq>")
        lines.append("    <priority>0.6</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")

    xml = "\n".join(lines)
    _sitemap_cache.set(cache_key, xml, _SITEMAP_TTL)
    return _xml_response(xml)
