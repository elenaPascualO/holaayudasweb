"""SQLite service for beneficiarios text search via FTS5."""

import asyncio
import logging
import re
import sqlite3
from pathlib import Path

from backend.config import BENEFICIARIOS_DB_PATH

logger = logging.getLogger(__name__)

# Shared connection (created on init)
_db_path: str = BENEFICIARIOS_DB_PATH


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


def init_db(db_path: str | None = None) -> None:
    """Initialize the database schema (idempotent).

    Creates the beneficiarios table, FTS5 virtual table,
    and sync_metadata table if they don't exist.

    Args:
        db_path: Override path (useful for tests).
    """
    path = db_path or _db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = _get_connection(path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS beneficiarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_persona INTEGER NOT NULL,
                beneficiario TEXT NOT NULL,
                nif_cif TEXT,
                nombre TEXT,
                ejercicio INTEGER NOT NULL,
                ayuda_e_total REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_beneficiarios_ejercicio
                ON beneficiarios(ejercicio);
            CREATE INDEX IF NOT EXISTS idx_beneficiarios_ayuda
                ON beneficiarios(ayuda_e_total DESC);

            CREATE TABLE IF NOT EXISTS sync_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        # FTS5 table — check if it exists before creating
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='beneficiarios_fts'"
        ).fetchone()
        if not row:
            conn.execute("""
                CREATE VIRTUAL TABLE beneficiarios_fts USING fts5(
                    nombre,
                    content='beneficiarios',
                    content_rowid='id',
                    tokenize='unicode61 remove_diacritics 2'
                )
            """)

        conn.commit()
    finally:
        conn.close()

    logger.info("Beneficiarios DB initialized at %s", path)


# Regex to extract NIF/CIF and name from the raw "beneficiario" field.
# Format: "ES A07129430 AIR EUROPA LINEAS AEREAS, SA"
# or:     "A07129430 SOME NAME"
# or:     "ES 123456789 SOME NAME" (person with DNI)
_BENEFICIARIO_RE = re.compile(
    r"^(?:ES\s+)?"          # optional "ES " country prefix
    r"([A-Z]?\d{7,8}[A-Z]?" # NIF/CIF: letter? + 7-8 digits + letter?
    r")\s+"                  # followed by space
    r"(.+)$",               # the rest is the name
    re.IGNORECASE,
)


def parse_beneficiario(raw: str) -> tuple[str | None, str | None]:
    """Extract NIF/CIF and clean name from the raw beneficiario string.

    Args:
        raw: Raw string like "ES A07129430 AIR EUROPA LINEAS AEREAS, SA".

    Returns:
        Tuple of (nif_cif, nombre). Both may be None if parsing fails.
    """
    if not raw:
        return None, None

    m = _BENEFICIARIO_RE.match(raw.strip())
    if m:
        return m.group(1).upper(), m.group(2).strip()

    return None, raw.strip()


def _build_fts_query(q: str) -> str:
    """Build an FTS5 MATCH query from user input.

    Each token is quoted to avoid FTS5 syntax errors.
    Example: 'air europa' → '"air" "europa"'

    Args:
        q: User search text.

    Returns:
        FTS5 MATCH expression.
    """
    # Strip quotes and special FTS characters
    cleaned = re.sub(r'["\'\*\(\)\-\+]', " ", q)
    tokens = cleaned.split()
    if not tokens:
        return ""
    return " ".join(f'"{t}"' for t in tokens)


def search_beneficiarios(
    q: str,
    anio: int | None = None,
    page: int = 0,
    page_size: int = 20,
    db_path: str | None = None,
) -> dict:
    """Search beneficiarios by name using FTS5.

    When anio is None, aggregates results by nif_cif (summing ayuda_e_total
    across years) to avoid duplicate entries per year.

    Args:
        q: Search text (e.g., "Air Europa").
        anio: Optional year filter. None = aggregate across all years.
        page: Page number (0-indexed).
        page_size: Results per page.
        db_path: Override path (useful for tests).

    Returns:
        Dict in BDNS-compatible paginated format:
        {content, totalElements, totalPages, number, size}
    """
    fts_query = _build_fts_query(q)
    if not fts_query:
        return _empty_response(page, page_size)

    conn = _get_connection(db_path)
    try:
        fts_filter = "b.id IN (SELECT rowid FROM beneficiarios_fts WHERE beneficiarios_fts MATCH ?)"
        params: list = [fts_query]

        if anio is not None:
            # Specific year: return individual rows (original behavior)
            where_clause = f"{fts_filter} AND b.ejercicio = ?"
            params.append(anio)

            count_sql = f"SELECT COUNT(*) FROM beneficiarios b WHERE {where_clause}"
            total = conn.execute(count_sql, params).fetchone()[0]

            if total == 0:
                return _empty_response(page, page_size)

            total_pages = max(1, (total + page_size - 1) // page_size)
            offset = page * page_size

            data_sql = f"""
                SELECT b.id_persona, b.beneficiario, b.nif_cif, b.nombre,
                       b.ejercicio, b.ayuda_e_total
                FROM beneficiarios b
                WHERE {where_clause}
                ORDER BY b.ayuda_e_total DESC
                LIMIT ? OFFSET ?
            """
            rows = conn.execute(data_sql, [*params, page_size, offset]).fetchall()

            content = [
                {
                    "idPersona": row["id_persona"],
                    "beneficiario": row["beneficiario"],
                    "nifCif": row["nif_cif"],
                    "nombre": row["nombre"],
                    "ejercicio": row["ejercicio"],
                    "ayudaETotal": row["ayuda_e_total"],
                }
                for row in rows
            ]
        else:
            # No year filter: aggregate by nif_cif across all years
            count_sql = f"""
                SELECT COUNT(DISTINCT b.nif_cif)
                FROM beneficiarios b
                WHERE {fts_filter} AND b.nif_cif IS NOT NULL
            """
            total = conn.execute(count_sql, params).fetchone()[0]

            if total == 0:
                return _empty_response(page, page_size)

            total_pages = max(1, (total + page_size - 1) // page_size)
            offset = page * page_size

            data_sql = f"""
                SELECT MAX(b.id_persona) as id_persona,
                       MAX(b.beneficiario) as beneficiario,
                       b.nif_cif,
                       MAX(b.nombre) as nombre,
                       SUM(b.ayuda_e_total) as ayuda_e_total
                FROM beneficiarios b
                WHERE {fts_filter} AND b.nif_cif IS NOT NULL
                GROUP BY b.nif_cif
                ORDER BY SUM(b.ayuda_e_total) DESC
                LIMIT ? OFFSET ?
            """
            rows = conn.execute(data_sql, [*params, page_size, offset]).fetchall()

            content = [
                {
                    "idPersona": row["id_persona"],
                    "beneficiario": row["beneficiario"],
                    "nifCif": row["nif_cif"],
                    "nombre": row["nombre"],
                    "ayudaETotal": row["ayuda_e_total"],
                }
                for row in rows
            ]

        return {
            "content": content,
            "totalElements": total,
            "totalPages": total_pages,
            "number": page,
            "size": page_size,
        }
    finally:
        conn.close()


async def search_beneficiarios_async(
    q: str,
    anio: int | None = None,
    page: int = 0,
    page_size: int = 20,
    db_path: str | None = None,
) -> dict:
    """Async wrapper for search_beneficiarios using to_thread.

    Args:
        q: Search text.
        anio: Optional year filter.
        page: Page number.
        page_size: Results per page.
        db_path: Override path.

    Returns:
        Paginated results dict.
    """
    return await asyncio.to_thread(
        search_beneficiarios, q, anio, page, page_size, db_path
    )


def get_top_beneficiarios_aggregated(
    page: int = 0,
    page_size: int = 20,
    db_path: str | None = None,
) -> dict:
    """Get top beneficiarios aggregated across all years.

    Groups by nif_cif and sums ayuda_e_total to produce a deduplicated
    ranking. Used when no year filter is selected.

    Args:
        page: Page number (0-indexed).
        page_size: Results per page.
        db_path: Override path (useful for tests).

    Returns:
        Dict in BDNS-compatible paginated format.
    """
    conn = _get_connection(db_path)
    try:
        total = conn.execute(
            "SELECT COUNT(DISTINCT nif_cif) FROM beneficiarios WHERE nif_cif IS NOT NULL"
        ).fetchone()[0]

        if total == 0:
            return _empty_response(page, page_size)

        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = page * page_size

        rows = conn.execute(
            """
            SELECT MAX(id_persona) as id_persona,
                   MAX(beneficiario) as beneficiario,
                   nif_cif,
                   MAX(nombre) as nombre,
                   SUM(ayuda_e_total) as ayuda_e_total
            FROM beneficiarios
            WHERE nif_cif IS NOT NULL
            GROUP BY nif_cif
            ORDER BY SUM(ayuda_e_total) DESC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        ).fetchall()

        content = [
            {
                "idPersona": row["id_persona"],
                "beneficiario": row["beneficiario"],
                "nifCif": row["nif_cif"],
                "nombre": row["nombre"],
                "ayudaETotal": row["ayuda_e_total"],
            }
            for row in rows
        ]

        return {
            "content": content,
            "totalElements": total,
            "totalPages": total_pages,
            "number": page,
            "size": page_size,
        }
    finally:
        conn.close()


async def get_top_beneficiarios_aggregated_async(
    page: int = 0,
    page_size: int = 20,
    db_path: str | None = None,
) -> dict:
    """Async wrapper for get_top_beneficiarios_aggregated.

    Args:
        page: Page number.
        page_size: Results per page.
        db_path: Override path.

    Returns:
        Paginated results dict.
    """
    return await asyncio.to_thread(
        get_top_beneficiarios_aggregated, page, page_size, db_path
    )


def sync_beneficiarios(records: list[dict], db_path: str | None = None) -> int:
    """Replace all beneficiarios data with new records.

    Runs in a single transaction: DELETE all → INSERT all → rebuild FTS.

    Args:
        records: List of dicts from BDNS API with keys:
            idPersona, beneficiario, ejercicio, ayudaETotal.
        db_path: Override path (useful for tests).

    Returns:
        Number of records inserted.
    """
    conn = _get_connection(db_path)
    try:
        conn.execute("BEGIN")

        # Clear existing data
        conn.execute("DELETE FROM beneficiarios")

        # Insert new records
        for rec in records:
            raw = rec.get("beneficiario", "")
            nif_cif, nombre = parse_beneficiario(raw)
            conn.execute(
                """INSERT INTO beneficiarios
                   (id_persona, beneficiario, nif_cif, nombre, ejercicio, ayuda_e_total)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    rec.get("idPersona", 0),
                    raw,
                    nif_cif,
                    nombre,
                    rec.get("ejercicio", 0),
                    rec.get("ayudaETotal", 0.0),
                ),
            )

        # Rebuild FTS index
        conn.execute("INSERT INTO beneficiarios_fts(beneficiarios_fts) VALUES('rebuild')")

        conn.commit()
        logger.info("Synced %d beneficiarios records", len(records))
        return len(records)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_sync_status(db_path: str | None = None) -> dict:
    """Get sync metadata (last sync timestamp, record count).

    Args:
        db_path: Override path (useful for tests).

    Returns:
        Dict with last_sync and total_records.
    """
    conn = _get_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM beneficiarios").fetchone()[0]

        row = conn.execute(
            "SELECT value FROM sync_metadata WHERE key = 'last_sync'"
        ).fetchone()
        last_sync = row["value"] if row else None

        return {"last_sync": last_sync, "total_records": total}
    finally:
        conn.close()


def get_beneficiarios_stats(db_path: str | None = None) -> dict:
    """Get detailed beneficiarios stats including per-year breakdown and sync deltas.

    Args:
        db_path: Override path (useful for tests).

    Returns:
        Dict with total_records, by_year breakdown, last sync info, and delta.
    """
    conn = _get_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM beneficiarios").fetchone()[0]

        # Per-year breakdown
        rows = conn.execute(
            "SELECT ejercicio, COUNT(*) as count, SUM(ayuda_e_total) as total_amount "
            "FROM beneficiarios GROUP BY ejercicio ORDER BY ejercicio DESC"
        ).fetchall()
        by_year = [
            {
                "year": row["ejercicio"],
                "records": row["count"],
                "total_amount": round(row["total_amount"] or 0, 2),
            }
            for row in rows
        ]

        # Distinct beneficiaries (unique nif_cif)
        distinct = conn.execute(
            "SELECT COUNT(DISTINCT nif_cif) FROM beneficiarios WHERE nif_cif IS NOT NULL"
        ).fetchone()[0]

        # Sync metadata
        last_sync_row = conn.execute(
            "SELECT value FROM sync_metadata WHERE key = 'last_sync'"
        ).fetchone()
        last_sync = last_sync_row["value"] if last_sync_row else None

        prev_count_row = conn.execute(
            "SELECT value FROM sync_metadata WHERE key = 'prev_total_records'"
        ).fetchone()
        prev_count = int(prev_count_row["value"]) if prev_count_row else None

        delta = total - prev_count if prev_count is not None else None

        return {
            "total_records": total,
            "distinct_beneficiaries": distinct,
            "by_year": by_year,
            "last_sync": last_sync,
            "previous_total_records": prev_count,
            "delta_records": delta,
        }
    finally:
        conn.close()


def get_top_beneficiarios_by_year(
    anio: int,
    page: int = 0,
    page_size: int = 20,
    db_path: str | None = None,
) -> dict:
    """Get top beneficiarios for a specific year from local SQLite.

    Args:
        anio: Year to filter.
        page: Page number (0-indexed).
        page_size: Results per page.
        db_path: Override path (useful for tests).

    Returns:
        Dict in BDNS-compatible paginated format.
    """
    conn = _get_connection(db_path)
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM beneficiarios WHERE ejercicio = ?",
            (anio,),
        ).fetchone()[0]

        if total == 0:
            return _empty_response(page, page_size)

        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = page * page_size

        rows = conn.execute(
            """SELECT id_persona, beneficiario, nif_cif, nombre,
                      ejercicio, ayuda_e_total
               FROM beneficiarios
               WHERE ejercicio = ?
               ORDER BY ayuda_e_total DESC
               LIMIT ? OFFSET ?""",
            (anio, page_size, offset),
        ).fetchall()

        content = [
            {
                "idPersona": row["id_persona"],
                "beneficiario": row["beneficiario"],
                "nifCif": row["nif_cif"],
                "nombre": row["nombre"],
                "ejercicio": row["ejercicio"],
                "ayudaETotal": row["ayuda_e_total"],
            }
            for row in rows
        ]

        return {
            "content": content,
            "totalElements": total,
            "totalPages": total_pages,
            "number": page,
            "size": page_size,
        }
    finally:
        conn.close()


async def get_top_beneficiarios_by_year_async(
    anio: int,
    page: int = 0,
    page_size: int = 20,
    db_path: str | None = None,
) -> dict:
    """Async wrapper for get_top_beneficiarios_by_year."""
    return await asyncio.to_thread(
        get_top_beneficiarios_by_year, anio, page, page_size, db_path,
    )


def get_beneficiario_by_nif(
    nif_cif: str,
    page: int = 0,
    page_size: int = 20,
    db_path: str | None = None,
) -> dict:
    """Get beneficiario records by NIF/CIF from local SQLite.

    Args:
        nif_cif: NIF or CIF identifier.
        page: Page number (0-indexed).
        page_size: Results per page.
        db_path: Override path (useful for tests).

    Returns:
        Dict in BDNS-compatible paginated format.
    """
    conn = _get_connection(db_path)
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM beneficiarios WHERE nif_cif = ?",
            (nif_cif,),
        ).fetchone()[0]

        if total == 0:
            return _empty_response(page, page_size)

        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = page * page_size

        rows = conn.execute(
            """SELECT id_persona, beneficiario, nif_cif, nombre,
                      ejercicio, ayuda_e_total
               FROM beneficiarios
               WHERE nif_cif = ?
               ORDER BY ejercicio DESC
               LIMIT ? OFFSET ?""",
            (nif_cif, page_size, offset),
        ).fetchall()

        content = [
            {
                "idPersona": row["id_persona"],
                "beneficiario": row["beneficiario"],
                "nifCif": row["nif_cif"],
                "nombre": row["nombre"],
                "ejercicio": row["ejercicio"],
                "ayudaETotal": row["ayuda_e_total"],
            }
            for row in rows
        ]

        return {
            "content": content,
            "totalElements": total,
            "totalPages": total_pages,
            "number": page,
            "size": page_size,
        }
    finally:
        conn.close()


async def get_beneficiario_by_nif_async(
    nif_cif: str,
    page: int = 0,
    page_size: int = 20,
    db_path: str | None = None,
) -> dict:
    """Async wrapper for get_beneficiario_by_nif."""
    return await asyncio.to_thread(
        get_beneficiario_by_nif, nif_cif, page, page_size, db_path,
    )


def get_available_years(db_path: str | None = None) -> list[int]:
    """Get distinct years available in the beneficiarios table.

    Args:
        db_path: Override path (useful for tests).

    Returns:
        List of years sorted descending.
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT ejercicio FROM beneficiarios ORDER BY ejercicio DESC"
        ).fetchall()
        return [row["ejercicio"] for row in rows]
    finally:
        conn.close()


async def get_available_years_async(db_path: str | None = None) -> list[int]:
    """Async wrapper for get_available_years."""
    return await asyncio.to_thread(get_available_years, db_path)


def has_data(db_path: str | None = None) -> bool:
    """Check if the beneficiarios table has any records.

    Args:
        db_path: Override path (useful for tests).

    Returns:
        True if there are records in the database.
    """
    conn = _get_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM beneficiarios").fetchone()[0]
        return total > 0
    finally:
        conn.close()


def _empty_response(page: int, page_size: int) -> dict:
    """Return an empty paginated response."""
    return {
        "content": [],
        "totalElements": 0,
        "totalPages": 0,
        "number": page,
        "size": page_size,
    }
