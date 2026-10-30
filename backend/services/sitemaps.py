"""Sitemap generation: XML builders and pregeneration to disk.

Sitemaps are generated in background (at startup if stale, after each daily
sync, or on demand via the admin API) and written gzip-compressed to
SITEMAPS_DIR, so routes can serve them in milliseconds. Building them from
SQLite is slow (it reads 600K+ rows), which is why it must never happen
inside a request on the event loop.

Layout:
    sitemap.xml                         index, lists all the files below
    sitemap-static.xml                  static pages
    sitemap-grants-open-{n}.xml         open grants, paginated
    sitemap-grants-closed-{year}[-{n}].xml  closed grants by year, paginated

Each file is stored as <name>.gz. The index is written last so it never
references files that don't exist yet.
"""

import gzip
import json
import logging
import math
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.config import SITE_BASE_URL, SITEMAPS_DIR
from backend.services.convocatorias_db import (
    get_sitemap_closed_by_year,
    get_sitemap_closed_entries,
    get_sitemap_open_count,
    get_sitemap_open_entries,
    get_sitemap_open_max_updated,
)

logger = logging.getLogger(__name__)

# Max URLs per sitemap file (sitemaps.org limit)
_GRANTS_PER_SITEMAP = 50000

INDEX_FILENAME = "sitemap.xml"
META_FILENAME = "sitemaps.meta.json"

STATIC_PAGES = [
    {"loc": "/", "changefreq": "daily", "priority": "1.0"},
    {"loc": "/buscar", "changefreq": "daily", "priority": "0.8"},
    {"loc": "/estadisticas", "changefreq": "weekly", "priority": "0.7"},
    {"loc": "/beneficiarios", "changefreq": "weekly", "priority": "0.7"},
    {"loc": "/contacto", "changefreq": "monthly", "priority": "0.3"},
    {"loc": "/como-funciona", "changefreq": "monthly", "priority": "0.4"},
]

# Valid sitemap names (anything else is rejected before touching the disk)
_NAME_RE = re.compile(
    r"^sitemap(-static|-grants-open-\d+|-grants-closed-\d{4}(-\d+)?)?\.xml$"
)

_gen_lock = threading.Lock()


def is_generating() -> bool:
    """Check if a sitemap generation is in progress."""
    return _gen_lock.locked()


def _resolve_dir(db_path: str | None, out_dir: str | None) -> str:
    """Return the sitemaps directory.

    When only db_path is overridden (tests), keep the files next to that DB.
    """
    if out_dir:
        return out_dir
    if db_path:
        return str(Path(db_path).parent / "sitemaps")
    return SITEMAPS_DIR


def _current_year() -> str:
    return str(datetime.now(timezone.utc).year)


# ---------------------------------------------------------------------------
# XML builders
# ---------------------------------------------------------------------------

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


def empty_urlset() -> str:
    """Return an empty <urlset> XML."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
    )


def build_static_xml() -> str:
    """Sitemap for static pages."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for page in STATIC_PAGES:
        lines.append("  <url>")
        lines.append(f"    <loc>{SITE_BASE_URL}{page['loc']}</loc>")
        lines.append(f"    <changefreq>{page['changefreq']}</changefreq>")
        lines.append(f"    <priority>{page['priority']}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines)


def build_open_xml(page: int, db_path: str | None = None) -> str:
    """Sitemap for one page (1-indexed) of open grants."""
    if page < 1:
        return empty_urlset()
    entries = get_sitemap_open_entries(page - 1, _GRANTS_PER_SITEMAP, db_path=db_path)
    return _build_urlset(entries, changefreq="weekly", priority="0.8")


def build_closed_xml(year: str, page: int, db_path: str | None = None) -> str:
    """Sitemap for one page (1-indexed) of closed grants of a year."""
    if page < 1:
        return empty_urlset()
    entries = get_sitemap_closed_entries(year, page - 1, _GRANTS_PER_SITEMAP, db_path=db_path)
    if year == _current_year():
        return _build_urlset(entries, changefreq="monthly", priority="0.4")
    return _build_urlset(entries, changefreq="yearly", priority="0.3")


def _plan(db_path: str | None) -> list[dict]:
    """List every sitemap file the index must reference, with its lastmod.

    Returns:
        List of {"name", "lastmod", "kind", "year", "page"} in index order.
    """
    open_count = get_sitemap_open_count(db_path=db_path)
    open_max_updated = get_sitemap_open_max_updated(db_path=db_path)
    closed_years = get_sitemap_closed_by_year(db_path=db_path)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    items = [{"name": "sitemap-static.xml", "lastmod": now_iso, "kind": "static"}]

    num_open_pages = max(1, math.ceil(open_count / _GRANTS_PER_SITEMAP))
    open_lastmod = open_max_updated[:10] if open_max_updated else now_iso
    for i in range(1, num_open_pages + 1):
        items.append({
            "name": f"sitemap-grants-open-{i}.xml",
            "lastmod": open_lastmod,
            "kind": "open",
            "page": i,
        })

    for year_info in closed_years:
        year = year_info["year"]
        last_mod = year_info["last_modified"]
        year_lastmod = last_mod[:10] if last_mod else now_iso
        num_pages = math.ceil(year_info["count"] / _GRANTS_PER_SITEMAP)
        for p in range(1, max(1, num_pages) + 1):
            suffix = f"{year}" if p == 1 else f"{year}-{p}"
            items.append({
                "name": f"sitemap-grants-closed-{suffix}.xml",
                "lastmod": year_lastmod,
                "kind": "closed",
                "year": year,
                "page": p,
            })

    return items


def _index_xml(items: list[dict]) -> str:
    """Build the <sitemapindex> XML for the planned files."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for item in items:
        lines.append("  <sitemap>")
        lines.append(f"    <loc>{SITE_BASE_URL}/{item['name']}</loc>")
        lines.append(f"    <lastmod>{item['lastmod']}</lastmod>")
        lines.append("  </sitemap>")
    lines.append("</sitemapindex>")
    return "\n".join(lines)


def build_index_xml(db_path: str | None = None) -> str:
    """Sitemap index listing static + open pages + closed-by-year pages."""
    return _index_xml(_plan(db_path))


def _build_item(item: dict, db_path: str | None) -> str:
    """Build the XML of one planned sitemap file."""
    if item["kind"] == "static":
        return build_static_xml()
    if item["kind"] == "open":
        return build_open_xml(item["page"], db_path=db_path)
    return build_closed_xml(item["year"], item["page"], db_path=db_path)


# ---------------------------------------------------------------------------
# Pregeneration to disk
# ---------------------------------------------------------------------------

def _write_atomic(path: str, data: bytes) -> None:
    """Write a file via temp file + rename so readers never see a partial file."""
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def generate_all(db_path: str | None = None, out_dir: str | None = None) -> dict:
    """Generate every sitemap file and write it gzip-compressed to disk.

    Skips if another generation is already running. The index is written
    after all the files it references; files no longer referenced are removed.

    Args:
        db_path: Override DB path (useful for tests).
        out_dir: Override output directory (useful for tests).

    Returns:
        {"status": "completed", "files", "urls", "elapsed_seconds"} or
        {"status": "skipped"}.
    """
    if not _gen_lock.acquire(blocking=False):
        logger.info("Sitemap generation already in progress — skipping")
        return {"status": "skipped"}

    try:
        directory = _resolve_dir(db_path, out_dir)
        os.makedirs(directory, exist_ok=True)
        start = time.monotonic()
        logger.info("Generating sitemaps in %s...", directory)

        items = _plan(db_path)
        written: set[str] = set()
        urls = 0
        for item in items:
            xml = _build_item(item, db_path)
            urls += xml.count("<url>")
            filename = item["name"] + ".gz"
            _write_atomic(os.path.join(directory, filename), gzip.compress(xml.encode("utf-8")))
            written.add(filename)

        index_filename = INDEX_FILENAME + ".gz"
        _write_atomic(
            os.path.join(directory, index_filename),
            gzip.compress(_index_xml(items).encode("utf-8")),
        )
        written.add(index_filename)

        for name in os.listdir(directory):
            stale_sitemap = name.endswith(".xml.gz") and name not in written
            if stale_sitemap or name.endswith(".tmp"):
                os.remove(os.path.join(directory, name))
                logger.info("Removed stale sitemap file %s", name)

        elapsed = round(time.monotonic() - start, 1)
        meta = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "files": len(written),
            "urls": urls,
            "elapsed_seconds": elapsed,
        }
        _write_atomic(os.path.join(directory, META_FILENAME), json.dumps(meta).encode("utf-8"))

        logger.info(
            "Sitemaps generated: %d files, %d URLs in %.1fs", len(written), urls, elapsed
        )
        return {"status": "completed", "files": len(written), "urls": urls, "elapsed_seconds": elapsed}
    finally:
        _gen_lock.release()


def _read_meta(directory: str) -> dict | None:
    """Return the generation metadata, or None if missing/unreadable."""
    try:
        with open(os.path.join(directory, META_FILENAME)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def needs_regeneration(out_dir: str | None = None, max_age_hours: int = 24) -> bool:
    """Check if sitemaps are missing or older than max_age_hours."""
    directory = _resolve_dir(None, out_dir)
    if not os.path.exists(os.path.join(directory, INDEX_FILENAME + ".gz")):
        return True
    meta = _read_meta(directory)
    if not meta or not meta.get("generated_at"):
        return True
    try:
        generated_at = datetime.fromisoformat(meta["generated_at"])
    except ValueError:
        return True
    return datetime.now(timezone.utc) - generated_at > timedelta(hours=max_age_hours)


def get_status(out_dir: str | None = None) -> dict:
    """Return generation status and metadata of the last generation."""
    directory = _resolve_dir(None, out_dir)
    meta = _read_meta(directory) or {}
    return {
        "generating": is_generating(),
        "generated_at": meta.get("generated_at"),
        "files": meta.get("files", 0),
        "urls": meta.get("urls", 0),
        "elapsed_seconds": meta.get("elapsed_seconds"),
        "directory": directory,
    }


def read_sitemap(filename: str, out_dir: str | None = None) -> bytes | None:
    """Return the gzip-compressed content of a pregenerated sitemap.

    Args:
        filename: Public name, e.g. "sitemap.xml" or "sitemap-grants-open-1.xml".
        out_dir: Override directory (useful for tests).

    Returns:
        Gzip bytes, or None if the name is invalid or the file doesn't exist.
    """
    if not _NAME_RE.match(filename):
        return None
    path = os.path.join(_resolve_dir(None, out_dir), filename + ".gz")
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None
