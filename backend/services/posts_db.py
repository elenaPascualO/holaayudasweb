"""SQLite service for generated social media posts."""

import asyncio
import json
import logging
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.config import CONVOCATORIAS_DB_PATH

logger = logging.getLogger(__name__)

# Reuse convocatorias DB (same file, new table)
_db_path: str = CONVOCATORIAS_DB_PATH


def _get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Create a new SQLite connection with WAL mode.

    Args:
        db_path: Override path (useful for tests). Defaults to config value.

    Returns:
        sqlite3.Connection with WAL and row_factory set.
    """
    path = db_path or _db_path
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_posts_db(db_path: str | None = None) -> None:
    """Initialize the generated_posts table (idempotent).

    Args:
        db_path: Override path (useful for tests).
    """
    path = db_path or _db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = _get_connection(path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS generated_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_type TEXT NOT NULL,
                content_x TEXT NOT NULL,
                content_linkedin TEXT NOT NULL,
                convocatoria_ids TEXT,
                metadata TEXT,
                status TEXT DEFAULT 'draft',
                published_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_posts_status
                ON generated_posts(status);
            CREATE INDEX IF NOT EXISTS idx_posts_type
                ON generated_posts(post_type, created_at DESC);
        """)
        conn.commit()
    finally:
        conn.close()

    logger.info("Posts DB initialized at %s", path)


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


def insert_post(
    post_type: str,
    content_x: str,
    content_linkedin: str,
    convocatoria_ids: list[int] | None = None,
    metadata: dict | None = None,
    db_path: str | None = None,
) -> int:
    """Insert a new post draft.

    Args:
        post_type: One of the 6 post types.
        content_x: Post content for X (300-600 chars).
        content_linkedin: Post content for LinkedIn (800-1500 chars).
        convocatoria_ids: List of convocatoria IDs used in this post.
        metadata: Extra context (theme, stats, curiosidad_type, etc.).
        db_path: Override path for tests.

    Returns:
        The ID of the inserted post.
    """
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute(
            """INSERT INTO generated_posts
               (post_type, content_x, content_linkedin, convocatoria_ids, metadata)
               VALUES (?, ?, ?, ?, ?)""",
            (
                post_type,
                content_x,
                content_linkedin,
                json.dumps(convocatoria_ids) if convocatoria_ids else None,
                json.dumps(metadata, ensure_ascii=False) if metadata else None,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def list_posts(
    status: str | None = None,
    post_type: str | None = None,
    limit: int = 20,
    db_path: str | None = None,
) -> list[dict]:
    """List posts with optional filters.

    Args:
        status: Filter by status ('draft', 'published', 'discarded').
        post_type: Filter by post type.
        limit: Max results (default 20).
        db_path: Override path for tests.

    Returns:
        List of post dicts ordered by created_at DESC.
    """
    conn = _get_connection(db_path)
    try:
        query = "SELECT * FROM generated_posts WHERE 1=1"
        params: list = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if post_type:
            query += " AND post_type = ?"
            params.append(post_type)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def get_post(post_id: int, db_path: str | None = None) -> dict | None:
    """Get a single post by ID.

    Args:
        post_id: The post ID.
        db_path: Override path for tests.

    Returns:
        Post dict or None if not found.
    """
    conn = _get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM generated_posts WHERE id = ?", (post_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_post_status(
    post_id: int,
    status: str,
    db_path: str | None = None,
) -> bool:
    """Update a post's status.

    Args:
        post_id: The post ID.
        status: New status ('published' or 'discarded').
        db_path: Override path for tests.

    Returns:
        True if the post was updated, False if not found.
    """
    conn = _get_connection(db_path)
    try:
        published_at = (
            datetime.now(timezone.utc).isoformat() if status == "published" else None
        )
        cursor = conn.execute(
            "UPDATE generated_posts SET status = ?, published_at = ? WHERE id = ?",
            (status, published_at, post_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_post(post_id: int, db_path: str | None = None) -> bool:
    """Delete a post.

    Args:
        post_id: The post ID.
        db_path: Override path for tests.

    Returns:
        True if deleted, False if not found.
    """
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute(
            "DELETE FROM generated_posts WHERE id = ?", (post_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_used_convocatoria_ids(db_path: str | None = None) -> set[int]:
    """Get all convocatoria IDs used in non-discarded posts.

    Args:
        db_path: Override path for tests.

    Returns:
        Set of convocatoria IDs already used.
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT convocatoria_ids FROM generated_posts WHERE status != 'discarded' AND convocatoria_ids IS NOT NULL"
        ).fetchall()
        ids: set[int] = set()
        for row in rows:
            try:
                ids.update(json.loads(row["convocatoria_ids"]))
            except (json.JSONDecodeError, TypeError):
                continue
        return ids
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict with parsed JSON fields."""
    d = dict(row)
    if d.get("convocatoria_ids"):
        try:
            d["convocatoria_ids"] = json.loads(d["convocatoria_ids"])
        except (json.JSONDecodeError, TypeError):
            pass
    if d.get("metadata"):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d


# ---------------------------------------------------------------------------
# Async wrappers
# ---------------------------------------------------------------------------


async def list_posts_async(
    status: str | None = None,
    post_type: str | None = None,
    limit: int = 20,
    db_path: str | None = None,
) -> list[dict]:
    """Async wrapper for list_posts."""
    return await asyncio.to_thread(list_posts, status, post_type, limit, db_path)


async def get_post_async(post_id: int, db_path: str | None = None) -> dict | None:
    """Async wrapper for get_post."""
    return await asyncio.to_thread(get_post, post_id, db_path)


async def update_post_status_async(
    post_id: int, status: str, db_path: str | None = None
) -> bool:
    """Async wrapper for update_post_status."""
    return await asyncio.to_thread(update_post_status, post_id, status, db_path)


async def delete_post_async(post_id: int, db_path: str | None = None) -> bool:
    """Async wrapper for delete_post."""
    return await asyncio.to_thread(delete_post, post_id, db_path)


# ---------------------------------------------------------------------------
# Data queries for post generation
# ---------------------------------------------------------------------------


def query_ayuda_destacada(
    exclude_ids: set[int] | None = None,
    db_path: str | None = None,
) -> dict | None:
    """Find one high-value open grant not previously featured.

    Picks the grant with the highest budget that is currently open
    and hasn't been used in a previous post.

    Args:
        exclude_ids: Convocatoria IDs to skip (from get_used_convocatoria_ids).
        db_path: Override path for tests.

    Returns:
        Dict with grant details or None if no suitable grant found.
    """
    exclude_ids = exclude_ids or set()
    conn = _get_connection(db_path)
    try:
        # Get top 10 by budget, then filter out used ones in Python
        # (SQLite doesn't handle large IN clauses well)
        rows = conn.execute(
            """SELECT id, numero_convocatoria, descripcion, presupuesto_total,
                      descripcion_finalidad, nivel2, fecha_fin_solicitud,
                      sede_electronica
               FROM convocatorias
               WHERE detail_fetched = 1
                 AND abierto = 1
                 AND (fecha_fin_solicitud IS NULL
                      OR fecha_fin_solicitud >= date('now'))
                 AND presupuesto_total > 0
               ORDER BY presupuesto_total DESC
               LIMIT 50""",
        ).fetchall()

        for row in rows:
            if row["id"] not in exclude_ids:
                return dict(row)
        return None
    finally:
        conn.close()


def query_datos_semana(db_path: str | None = None) -> dict:
    """Aggregate stats for the past 7 days.

    Args:
        db_path: Override path for tests.

    Returns:
        Dict with new_count, total_budget, top_region, top_theme, total_open.
    """
    conn = _get_connection(db_path)
    try:
        # New grants this week
        row = conn.execute(
            """SELECT COUNT(*) as new_count,
                      COALESCE(SUM(presupuesto_total), 0) as total_budget
               FROM convocatorias
               WHERE fecha_recepcion >= date('now', '-7 days')
                 AND detail_fetched = 1"""
        ).fetchone()
        new_count = row["new_count"]
        total_budget = row["total_budget"]

        # Top theme this week
        theme_row = conn.execute(
            """SELECT descripcion_finalidad, COUNT(*) as cnt
               FROM convocatorias
               WHERE fecha_recepcion >= date('now', '-7 days')
                 AND detail_fetched = 1
                 AND descripcion_finalidad IS NOT NULL
               GROUP BY descripcion_finalidad
               ORDER BY cnt DESC LIMIT 1"""
        ).fetchone()
        top_theme = theme_row["descripcion_finalidad"] if theme_row else None

        # Top region this week (parse regiones_json)
        region_row = conn.execute(
            """SELECT j.value ->> 'descripcion' as region, COUNT(*) as cnt
               FROM convocatorias c, json_each(c.regiones_json) j
               WHERE c.fecha_recepcion >= date('now', '-7 days')
                 AND c.detail_fetched = 1
                 AND c.regiones_json IS NOT NULL
               GROUP BY region
               ORDER BY cnt DESC LIMIT 1"""
        ).fetchone()
        top_region = region_row["region"] if region_row else None

        # Total currently open
        open_row = conn.execute(
            """SELECT COUNT(*) as total_open
               FROM convocatorias
               WHERE detail_fetched = 1
                 AND abierto = 1
                 AND (fecha_fin_solicitud IS NULL
                      OR fecha_fin_solicitud >= date('now'))"""
        ).fetchone()
        total_open = open_row["total_open"]

        return {
            "new_count": new_count,
            "total_budget": total_budget,
            "top_region": top_region,
            "top_theme": top_theme,
            "total_open": total_open,
        }
    finally:
        conn.close()


def query_cierre_inminente(
    days: int = 7,
    limit: int = 10,
    db_path: str | None = None,
) -> list[dict]:
    """Find grants closing within N days.

    Excludes generic end-of-year dates (%-12-31).

    Args:
        days: Number of days ahead to look.
        limit: Max results.
        db_path: Override path for tests.

    Returns:
        List of grant dicts ordered by fecha_fin_solicitud ASC.
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT id, numero_convocatoria, descripcion, presupuesto_total,
                      fecha_fin_solicitud, descripcion_finalidad, nivel2
               FROM convocatorias
               WHERE detail_fetched = 1
                 AND fecha_fin_solicitud BETWEEN date('now') AND date('now', ? || ' days')
                 AND fecha_fin_solicitud NOT LIKE '%-12-31'
               ORDER BY fecha_fin_solicitud ASC
               LIMIT ?""",
            (str(days), limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def query_tematico(
    exclude_ids: set[int] | None = None,
    db_path: str | None = None,
) -> dict | None:
    """Pick a theme with open grants and return a selection.

    Chooses the finalidad with the most currently-open grants
    that hasn't been used in the last 30 days of tematico posts.

    Args:
        exclude_ids: Convocatoria IDs to skip.
        db_path: Override path for tests.

    Returns:
        Dict with theme name and list of grants, or None.
    """
    exclude_ids = exclude_ids or set()
    conn = _get_connection(db_path)
    try:
        # Get recently used themes (last 30 days)
        recent_themes: set[str] = set()
        meta_rows = conn.execute(
            """SELECT metadata FROM generated_posts
               WHERE post_type = 'tematico'
                 AND status != 'discarded'
                 AND created_at >= datetime('now', '-30 days')
                 AND metadata IS NOT NULL"""
        ).fetchall()
        for meta_row in meta_rows:
            try:
                meta = json.loads(meta_row["metadata"])
                if meta.get("theme"):
                    recent_themes.add(meta["theme"])
            except (json.JSONDecodeError, TypeError):
                continue

        # Find themes with most open grants (exclude junk finalidades)
        theme_rows = conn.execute(
            """SELECT descripcion_finalidad, COUNT(*) as cnt
               FROM convocatorias
               WHERE detail_fetched = 1
                 AND abierto = 1
                 AND (fecha_fin_solicitud IS NULL
                      OR fecha_fin_solicitud >= date('now'))
                 AND descripcion_finalidad IS NOT NULL
                 AND descripcion_finalidad NOT LIKE '%no disponible%'
                 AND presupuesto_total > 0
                 AND nivel2 IS NOT NULL
               GROUP BY descripcion_finalidad
               ORDER BY cnt DESC
               LIMIT 20"""
        ).fetchall()

        # Pick first theme not recently used
        chosen_theme = None
        for theme_row in theme_rows:
            if theme_row["descripcion_finalidad"] not in recent_themes:
                chosen_theme = theme_row["descripcion_finalidad"]
                break

        if not chosen_theme:
            # Fallback: use the most popular theme regardless
            if theme_rows:
                chosen_theme = theme_rows[0]["descripcion_finalidad"]
            else:
                return None

        # Get grants for this theme (only with useful data)
        grant_rows = conn.execute(
            """SELECT id, numero_convocatoria, descripcion, presupuesto_total,
                      descripcion_finalidad, nivel2, fecha_fin_solicitud
               FROM convocatorias
               WHERE detail_fetched = 1
                 AND abierto = 1
                 AND (fecha_fin_solicitud IS NULL
                      OR fecha_fin_solicitud >= date('now'))
                 AND descripcion_finalidad = ?
                 AND presupuesto_total > 0
                 AND nivel2 IS NOT NULL
               ORDER BY presupuesto_total DESC
               LIMIT 20""",
            (chosen_theme,),
        ).fetchall()

        # Filter out used IDs
        grants = [dict(r) for r in grant_rows if r["id"] not in exclude_ids][:5]

        if not grants:
            return None

        return {
            "theme": chosen_theme,
            "grants": grants,
        }
    finally:
        conn.close()


def query_top_organismo(db_path: str | None = None) -> dict | None:
    """Find the organism that published most grants this week.

    Args:
        db_path: Override path for tests.

    Returns:
        Dict with organism name, count, and example grants, or None.
    """
    conn = _get_connection(db_path)
    try:
        # Top organism by grant count this week
        org_row = conn.execute(
            """SELECT nivel2, COUNT(*) as cnt,
                      COALESCE(SUM(presupuesto_total), 0) as total_budget
               FROM convocatorias
               WHERE fecha_recepcion >= date('now', '-7 days')
                 AND detail_fetched = 1
                 AND nivel2 IS NOT NULL
               GROUP BY nivel2
               ORDER BY cnt DESC
               LIMIT 1"""
        ).fetchone()

        if not org_row:
            return None

        organism = org_row["nivel2"]

        # Get example grants from this organism
        grant_rows = conn.execute(
            """SELECT id, numero_convocatoria, descripcion, presupuesto_total,
                      descripcion_finalidad, fecha_fin_solicitud
               FROM convocatorias
               WHERE fecha_recepcion >= date('now', '-7 days')
                 AND detail_fetched = 1
                 AND nivel2 = ?
               ORDER BY presupuesto_total DESC
               LIMIT 5""",
            (organism,),
        ).fetchall()

        return {
            "organism": organism,
            "count": org_row["cnt"],
            "total_budget": org_row["total_budget"],
            "grants": [dict(r) for r in grant_rows],
        }
    finally:
        conn.close()


# Pool of curiosity queries — each returns a dict with type + data
_CURIOSIDAD_QUERIES: list[tuple[str, str]] = [
    (
        "mayor_presupuesto_historico",
        """SELECT numero_convocatoria, descripcion, presupuesto_total, nivel2,
                  fecha_recepcion
           FROM convocatorias
           WHERE detail_fetched = 1 AND presupuesto_total > 0
           ORDER BY presupuesto_total DESC LIMIT 1""",
    ),
    (
        "ano_record",
        """SELECT strftime('%Y', fecha_recepcion) as year,
                  COUNT(*) as cnt,
                  COALESCE(SUM(presupuesto_total), 0) as budget
           FROM convocatorias
           WHERE detail_fetched = 1 AND fecha_recepcion IS NOT NULL
           GROUP BY year ORDER BY cnt DESC LIMIT 1""",
    ),
    (
        "ano_record_presupuesto",
        """SELECT strftime('%Y', fecha_recepcion) as year,
                  COALESCE(SUM(presupuesto_total), 0) as budget,
                  COUNT(*) as cnt
           FROM convocatorias
           WHERE detail_fetched = 1 AND fecha_recepcion IS NOT NULL
           GROUP BY year ORDER BY budget DESC LIMIT 1""",
    ),
    (
        "organismo_mas_activo",
        """SELECT nivel2, COUNT(*) as cnt,
                  COALESCE(SUM(presupuesto_total), 0) as budget
           FROM convocatorias
           WHERE detail_fetched = 1 AND nivel2 IS NOT NULL
           GROUP BY nivel2 ORDER BY cnt DESC LIMIT 1""",
    ),
    (
        "region_mas_ayudas",
        """SELECT j.value ->> 'descripcion' as region, COUNT(*) as cnt
           FROM convocatorias c, json_each(c.regiones_json) j
           WHERE c.detail_fetched = 1 AND c.regiones_json IS NOT NULL
           GROUP BY region ORDER BY cnt DESC LIMIT 1""",
    ),
    (
        "tema_mas_presupuesto",
        """SELECT descripcion_finalidad,
                  COALESCE(SUM(presupuesto_total), 0) as budget,
                  COUNT(*) as cnt
           FROM convocatorias
           WHERE detail_fetched = 1
                 AND descripcion_finalidad IS NOT NULL
                 AND presupuesto_total > 0
           GROUP BY descripcion_finalidad
           ORDER BY budget DESC LIMIT 1""",
    ),
    (
        "media_presupuesto_anual",
        """SELECT strftime('%Y', fecha_recepcion) as year,
                  ROUND(AVG(presupuesto_total), 2) as avg_budget,
                  COUNT(*) as cnt
           FROM convocatorias
           WHERE detail_fetched = 1
                 AND presupuesto_total > 0
                 AND fecha_recepcion IS NOT NULL
           GROUP BY year
           ORDER BY avg_budget DESC LIMIT 1""",
    ),
]


def query_dato_curioso(db_path: str | None = None) -> dict | None:
    """Run a random curiosity query not used recently.

    Checks metadata.curiosidad_type in recent posts to avoid repetition.

    Args:
        db_path: Override path for tests.

    Returns:
        Dict with curiosidad_type and query results, or None.
    """
    conn = _get_connection(db_path)
    try:
        # Get recently used curiosity types (last 60 days)
        recent_types: set[str] = set()
        meta_rows = conn.execute(
            """SELECT metadata FROM generated_posts
               WHERE post_type = 'dato_curioso'
                 AND status != 'discarded'
                 AND created_at >= datetime('now', '-60 days')
                 AND metadata IS NOT NULL"""
        ).fetchall()
        for meta_row in meta_rows:
            try:
                meta = json.loads(meta_row["metadata"])
                if meta.get("curiosidad_type"):
                    recent_types.add(meta["curiosidad_type"])
            except (json.JSONDecodeError, TypeError):
                continue

        # Filter out recently used queries
        available = [
            (qtype, sql) for qtype, sql in _CURIOSIDAD_QUERIES
            if qtype not in recent_types
        ]
        if not available:
            # All used recently — reset and pick any
            available = list(_CURIOSIDAD_QUERIES)

        # Pick one at random
        random.shuffle(available)

        for qtype, sql in available:
            row = conn.execute(sql).fetchone()
            if row:
                return {
                    "curiosidad_type": qtype,
                    "data": dict(row),
                }

        return None
    finally:
        conn.close()
