"""SQLite service for convocatorias local replica with FTS5 and embeddings."""

import asyncio
import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from backend.config import CONVOCATORIAS_DB_PATH

logger = logging.getLogger(__name__)

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


def init_convocatorias_db(db_path: str | None = None) -> None:
    """Initialize the database schema (idempotent).

    Creates the convocatorias table, FTS5 virtual table,
    indexes, and sync_metadata table if they don't exist.

    Args:
        db_path: Override path (useful for tests).
    """
    path = db_path or _db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = _get_connection(path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS convocatorias (
                id INTEGER PRIMARY KEY,
                numero_convocatoria TEXT NOT NULL UNIQUE,
                descripcion TEXT NOT NULL,
                descripcion_leng TEXT,
                fecha_recepcion TEXT,
                nivel1 TEXT,
                nivel2 TEXT,
                nivel3 TEXT,

                detail_fetched INTEGER DEFAULT 0,
                presupuesto_total REAL,
                descripcion_finalidad TEXT,
                finalidad_id INTEGER,
                abierto INTEGER,
                fecha_inicio_solicitud TEXT,
                fecha_fin_solicitud TEXT,
                regiones_json TEXT,
                instrumentos_json TEXT,
                tipos_beneficiarios_json TEXT,
                sectores_json TEXT,
                objetivos_json TEXT,
                documentos_json TEXT,
                anuncios_json TEXT,
                sede_electronica TEXT,
                url_bases_reguladoras TEXT,
                descripcion_bases_reguladoras TEXT,
                tipo_convocatoria TEXT,
                text_inicio TEXT,
                text_fin TEXT,

                embedding BLOB,
                embedding_version INTEGER DEFAULT 0,

                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_conv_fecha
                ON convocatorias(fecha_recepcion DESC);
            CREATE INDEX IF NOT EXISTS idx_conv_detail
                ON convocatorias(detail_fetched);
            CREATE INDEX IF NOT EXISTS idx_conv_finalidad
                ON convocatorias(finalidad_id);
            CREATE INDEX IF NOT EXISTS idx_conv_abierto
                ON convocatorias(abierto);
            CREATE INDEX IF NOT EXISTS idx_conv_numero
                ON convocatorias(numero_convocatoria);

            CREATE TABLE IF NOT EXISTS conv_sync_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        # FTS5 table — check if it exists before creating
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='convocatorias_fts'"
        ).fetchone()
        if not row:
            conn.execute("""
                CREATE VIRTUAL TABLE convocatorias_fts USING fts5(
                    descripcion, descripcion_leng, descripcion_finalidad,
                    nivel1, nivel2, nivel3,
                    content='convocatorias', content_rowid='id',
                    tokenize='unicode61 remove_diacritics 2'
                )
            """)

        conn.commit()
    finally:
        conn.close()

    logger.info("Convocatorias DB initialized at %s", path)


def _build_fts_query(q: str) -> str:
    """Build an FTS5 MATCH query from user input.

    Each token is quoted and joined with implicit AND.
    Example: 'ayudas diabetes pamplona' → '"ayudas" "diabetes" "pamplona"'

    Args:
        q: User search text.

    Returns:
        FTS5 MATCH expression.
    """
    cleaned = re.sub(r'["\'\*\(\)\-\+]', " ", q)
    tokens = cleaned.split()
    if not tokens:
        return ""
    return " ".join(f'"{t}"' for t in tokens)


def upsert_convocatorias_list(
    records: list[dict], db_path: str | None = None
) -> int:
    """Insert convocatorias from a BDNS list response (INSERT OR IGNORE).

    Only inserts basic list-level fields. Does not overwrite detail data.

    Args:
        records: List of dicts from BDNS search/ultimas with keys:
            numeroConvocatoria, descripcion, descripcionLeng, fechaRecepcion,
            organo: {nivel1, nivel2, nivel3}.
        db_path: Override path (useful for tests).

    Returns:
        Number of records inserted (new ones only).
    """
    conn = _get_connection(db_path)
    inserted = 0
    try:
        for rec in records:
            organo = rec.get("organo") or {}
            fecha = rec.get("fechaRecepcion", "")
            # Convert dd/mm/yyyy to ISO if needed
            if fecha and "/" in fecha:
                parts = fecha.split("/")
                if len(parts) == 3:
                    fecha = f"{parts[2]}-{parts[1]}-{parts[0]}"

            cursor = conn.execute(
                """INSERT OR IGNORE INTO convocatorias
                   (numero_convocatoria, descripcion, descripcion_leng,
                    fecha_recepcion, nivel1, nivel2, nivel3)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(rec.get("numeroConvocatoria", "")),
                    rec.get("descripcion", ""),
                    rec.get("descripcionLeng"),
                    fecha,
                    organo.get("nivel1"),
                    organo.get("nivel2"),
                    organo.get("nivel3"),
                ),
            )
            inserted += cursor.rowcount

        conn.commit()
        logger.info("Upserted %d new convocatorias (of %d provided)", inserted, len(records))
        return inserted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_convocatoria_detail(
    numero: str, detail: dict, db_path: str | None = None
) -> bool:
    """Update a convocatoria with full detail data from BDNS.

    Args:
        numero: Convocatoria number (e.g., "886707").
        detail: Full detail dict from BDNS API.
        db_path: Override path (useful for tests).

    Returns:
        True if a row was updated.
    """
    conn = _get_connection(db_path)
    try:
        regiones = detail.get("regiones") or []
        instrumentos = detail.get("instrumentos") or []
        tipos_benef = detail.get("tiposBeneficiarios") or []
        sectores = detail.get("sectores") or []
        objetivos = detail.get("objetivos") or []
        documentos = detail.get("documentos") or []
        anuncios = detail.get("anuncios") or []

        finalidad_id = None
        if detail.get("finalidad"):
            finalidad_id = detail["finalidad"].get("id") if isinstance(detail["finalidad"], dict) else detail["finalidad"]

        cursor = conn.execute(
            """UPDATE convocatorias SET
                detail_fetched = 1,
                presupuesto_total = ?,
                descripcion_finalidad = ?,
                finalidad_id = ?,
                abierto = ?,
                fecha_inicio_solicitud = ?,
                fecha_fin_solicitud = ?,
                regiones_json = ?,
                instrumentos_json = ?,
                tipos_beneficiarios_json = ?,
                sectores_json = ?,
                objetivos_json = ?,
                documentos_json = ?,
                anuncios_json = ?,
                sede_electronica = ?,
                url_bases_reguladoras = ?,
                descripcion_bases_reguladoras = ?,
                tipo_convocatoria = ?,
                text_inicio = ?,
                text_fin = ?,
                updated_at = datetime('now')
               WHERE numero_convocatoria = ?""",
            (
                detail.get("presupuestoTotal"),
                detail.get("descripcionFinalidad"),
                finalidad_id,
                1 if detail.get("abierto") else 0,
                detail.get("fechaInicioSolicitud"),
                detail.get("fechaFinSolicitud"),
                json.dumps(regiones, ensure_ascii=False) if regiones else None,
                json.dumps(instrumentos, ensure_ascii=False) if instrumentos else None,
                json.dumps(tipos_benef, ensure_ascii=False) if tipos_benef else None,
                json.dumps(sectores, ensure_ascii=False) if sectores else None,
                json.dumps(objetivos, ensure_ascii=False) if objetivos else None,
                json.dumps(documentos, ensure_ascii=False) if documentos else None,
                json.dumps(anuncios, ensure_ascii=False) if anuncios else None,
                detail.get("sedeElectronica"),
                detail.get("urlBasesReguladoras"),
                detail.get("descripcionBasesReguladoras"),
                detail.get("tipoConvocatoria"),
                detail.get("textInicio"),
                detail.get("textFin"),
                numero,
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_unfetched_detail_ids(
    limit: int = 3000, db_path: str | None = None
) -> list[str]:
    """Get convocatoria numbers that don't have detail data yet.

    Args:
        limit: Maximum number to return.
        db_path: Override path (useful for tests).

    Returns:
        List of numero_convocatoria strings.
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT numero_convocatoria FROM convocatorias WHERE detail_fetched = 0 LIMIT ?",
            (limit,),
        ).fetchall()
        return [row["numero_convocatoria"] for row in rows]
    finally:
        conn.close()


def get_unembedded_ids(
    limit: int = 500, db_path: str | None = None
) -> list[tuple[int, str]]:
    """Get convocatorias with detail but no embedding.

    Args:
        limit: Maximum number to return.
        db_path: Override path (useful for tests).

    Returns:
        List of (id, numero_convocatoria) tuples.
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT id, numero_convocatoria FROM convocatorias
               WHERE detail_fetched = 1 AND embedding IS NULL
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [(row["id"], row["numero_convocatoria"]) for row in rows]
    finally:
        conn.close()


def store_embeddings(
    records: list[tuple[int, bytes]], db_path: str | None = None
) -> int:
    """Store embedding BLOBs for convocatorias.

    Args:
        records: List of (id, embedding_blob) tuples.
        db_path: Override path (useful for tests).

    Returns:
        Number of rows updated.
    """
    conn = _get_connection(db_path)
    updated = 0
    try:
        for conv_id, blob in records:
            cursor = conn.execute(
                """UPDATE convocatorias SET embedding = ?, embedding_version = 1,
                   updated_at = datetime('now') WHERE id = ?""",
                (blob, conv_id),
            )
            updated += cursor.rowcount
        conn.commit()
        return updated
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_backfill_stats(db_path: str | None = None) -> dict:
    """Return counts for monitoring backfill progress.

    Returns:
        Dict with total, with_detail, with_embedding, pending_detail,
        pending_embedding counts.
    """
    conn = _get_connection(db_path)
    try:
        row = conn.execute(
            """SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN detail_fetched = 1 THEN 1 ELSE 0 END) AS with_detail,
                SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) AS with_embedding
            FROM convocatorias"""
        ).fetchone()
        total = row["total"]
        with_detail = row["with_detail"]
        with_embedding = row["with_embedding"]
        return {
            "total_convocatorias": total,
            "with_detail": with_detail,
            "with_embedding": with_embedding,
            "pending_detail": total - with_detail,
            "pending_embedding": with_detail - with_embedding,
        }
    finally:
        conn.close()


def rebuild_fts(db_path: str | None = None) -> None:
    """Rebuild the FTS5 index from the convocatorias table.

    Args:
        db_path: Override path (useful for tests).
    """
    conn = _get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO convocatorias_fts(convocatorias_fts) VALUES('rebuild')"
        )
        conn.commit()
        logger.info("FTS5 index rebuilt")
    finally:
        conn.close()


def get_sync_status(db_path: str | None = None) -> dict:
    """Get sync metadata (counts and last sync timestamp).

    Args:
        db_path: Override path (useful for tests).

    Returns:
        Dict with total, with_detail, with_embedding, last_sync.
    """
    conn = _get_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM convocatorias").fetchone()[0]
        with_detail = conn.execute(
            "SELECT COUNT(*) FROM convocatorias WHERE detail_fetched = 1"
        ).fetchone()[0]
        with_embedding = conn.execute(
            "SELECT COUNT(*) FROM convocatorias WHERE embedding IS NOT NULL"
        ).fetchone()[0]

        row = conn.execute(
            "SELECT value FROM conv_sync_metadata WHERE key = 'last_sync'"
        ).fetchone()
        last_sync = row["value"] if row else None

        return {
            "total": total,
            "with_detail": with_detail,
            "with_embedding": with_embedding,
            "last_sync": last_sync,
        }
    finally:
        conn.close()


def search_fts(
    query: str, limit: int = 500, db_path: str | None = None
) -> list[dict]:
    """Pre-filter convocatorias by FTS5 text search.

    Returns basic data + rowid for embedding lookup.

    Args:
        query: User search text.
        limit: Max candidates to return.
        db_path: Override path (useful for tests).

    Returns:
        List of dicts with convocatoria data.
    """
    fts_query = _build_fts_query(query)
    if not fts_query:
        return []

    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT c.id, c.numero_convocatoria, c.descripcion, c.descripcion_leng,
                      c.fecha_recepcion, c.nivel1, c.nivel2, c.nivel3,
                      c.presupuesto_total, c.abierto, c.embedding,
                      c.descripcion_finalidad, c.finalidad_id,
                      c.fecha_inicio_solicitud, c.fecha_fin_solicitud,
                      c.text_inicio, c.text_fin
               FROM convocatorias c
               WHERE c.id IN (
                   SELECT rowid FROM convocatorias_fts
                   WHERE convocatorias_fts MATCH ?
               )
               AND c.detail_fetched = 1
               ORDER BY c.fecha_recepcion DESC
               LIMIT ?""",
            (fts_query, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_recent_with_embeddings(
    limit: int = 5000, db_path: str | None = None
) -> list[dict]:
    """Get recent convocatorias that have embeddings (for fallback search).

    Args:
        limit: Max results.
        db_path: Override path (useful for tests).

    Returns:
        List of dicts with convocatoria data.
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT c.id, c.numero_convocatoria, c.descripcion, c.descripcion_leng,
                      c.fecha_recepcion, c.nivel1, c.nivel2, c.nivel3,
                      c.presupuesto_total, c.abierto, c.embedding,
                      c.descripcion_finalidad, c.finalidad_id,
                      c.fecha_inicio_solicitud, c.fecha_fin_solicitud,
                      c.text_inicio, c.text_fin
               FROM convocatorias c
               WHERE c.embedding IS NOT NULL
               ORDER BY c.fecha_recepcion DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_convocatoria_detail_local(
    numero: str, db_path: str | None = None
) -> dict | None:
    """Get full convocatoria detail from local SQLite, formatted like BDNS API.

    Args:
        numero: Convocatoria number (e.g., "886707").
        db_path: Override path (useful for tests).

    Returns:
        Dict in BDNS-compatible format, or None if not found or no detail.
    """
    conn = _get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM convocatorias WHERE numero_convocatoria = ? AND detail_fetched = 1",
            (numero,),
        ).fetchone()
        if not row:
            return None

        return _row_to_bdns_detail(row)
    finally:
        conn.close()


def _row_to_bdns_detail(row: sqlite3.Row) -> dict:
    """Convert a SQLite row to BDNS-compatible detail format.

    Args:
        row: SQLite row from convocatorias table.

    Returns:
        Dict matching the BDNS detail API format.
    """
    result = {
        "codigoBDNS": row["numero_convocatoria"],
        "descripcion": row["descripcion"],
        "descripcionLeng": row["descripcion_leng"],
        "fechaRecepcion": row["fecha_recepcion"],
        "organo": {
            "nivel1": row["nivel1"],
            "nivel2": row["nivel2"],
            "nivel3": row["nivel3"],
        },
        "presupuestoTotal": row["presupuesto_total"],
        "descripcionFinalidad": row["descripcion_finalidad"],
        "abierto": bool(row["abierto"]) if row["abierto"] is not None else None,
        "fechaInicioSolicitud": row["fecha_inicio_solicitud"],
        "fechaFinSolicitud": row["fecha_fin_solicitud"],
        "sedeElectronica": row["sede_electronica"],
        "urlBasesReguladoras": row["url_bases_reguladoras"],
        "descripcionBasesReguladoras": row["descripcion_bases_reguladoras"],
        "tipoConvocatoria": row["tipo_convocatoria"],
        "textInicio": row["text_inicio"],
        "textFin": row["text_fin"],
    }

    # Parse JSON arrays
    for field, key in [
        ("regiones_json", "regiones"),
        ("instrumentos_json", "instrumentos"),
        ("tipos_beneficiarios_json", "tiposBeneficiarios"),
        ("sectores_json", "sectores"),
        ("objetivos_json", "objetivos"),
        ("documentos_json", "documentos"),
        ("anuncios_json", "anuncios"),
    ]:
        raw = row[field]
        result[key] = json.loads(raw) if raw else []

    return result


def _parse_iso_date(date_str: str | None) -> datetime | None:
    """Parse ISO date (YYYY-MM-DD) from SQLite into datetime."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _compute_status(
    abierto: int | None,
    start_str: str | None,
    end_str: str | None,
) -> str:
    """Compute grant status from dates and abierto flag.

    Mirrors getGrantStatus() in frontend/src/utils/dates.js and
    get_grant_status() in bdns_client.py.
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Permanently open with no end date
    if abierto == 1 and not end_str:
        return "permanent"

    end_date = _parse_iso_date(end_str)
    start_date = _parse_iso_date(start_str)

    # End date in the past → closed
    if end_date and end_date < today:
        return "closed"

    # Start date in the future → upcoming
    if start_date and start_date > today:
        return "upcoming"

    # End date in the future → open
    if end_date and end_date >= today:
        return "open"

    # Fallback: abierto=true means "indefinitely open"
    if abierto == 1:
        return "open"

    # No parseable dates and not marked as indefinite → unknown
    return "unknown"


def _row_to_search_result(row: sqlite3.Row) -> dict:
    """Convert a SQLite row to BDNS-compatible search result format.

    Args:
        row: SQLite row from convocatorias table.

    Returns:
        Dict matching the BDNS search result format used by GrantCard.
    """
    # Determine status using date-based logic (mirrors getGrantStatus in dates.js)
    abierto = row["abierto"] if "abierto" in row.keys() else None
    keys = row.keys()
    fin_str = row["fecha_fin_solicitud"] if "fecha_fin_solicitud" in keys else None
    inicio_str = row["fecha_inicio_solicitud"] if "fecha_inicio_solicitud" in keys else None
    text_inicio = row["text_inicio"] if "text_inicio" in keys else None
    text_fin = row["text_fin"] if "text_fin" in keys else None

    status = _compute_status(abierto, inicio_str or text_inicio, fin_str or text_fin)

    return {
        "numeroConvocatoria": row["numero_convocatoria"],
        "descripcion": row["descripcion"],
        "descripcionLeng": row["descripcion_leng"] if "descripcion_leng" in row.keys() else None,
        "fechaRecepcion": row["fecha_recepcion"],
        # Top-level fields for GrantCard.js (uses grant.nivel1, grant.nivel2)
        "nivel1": row["nivel1"],
        "nivel2": row["nivel2"],
        "nivel3": row["nivel3"],
        # Nested organo for detail page compatibility
        "organo": {
            "nivel1": row["nivel1"],
            "nivel2": row["nivel2"],
            "nivel3": row["nivel3"],
        },
        "_presupuestoTotal": row["presupuesto_total"],
        "_status": status,
    }


# --- Local-first query functions ---

# Comunidades autónomas for tipo_administracion='A' filter
_COMUNIDADES_AUTONOMAS = {
    "ANDALUCIA", "ARAGON", "ASTURIAS", "BALEARS", "CANARIAS",
    "CANTABRIA", "CASTILLA - LA MANCHA", "CASTILLA Y LEON",
    "CATALUÑA", "COMUNITAT VALENCIANA", "EXTREMADURA",
    "GALICIA", "LA RIOJA", "MADRID", "MURCIA", "NAVARRA",
    "PAIS VASCO", "CEUTA", "MELILLA",
}


def has_convocatorias_data(db_path: str | None = None) -> bool:
    """Check if the convocatorias table has detail-fetched records.

    Args:
        db_path: Override path (useful for tests).

    Returns:
        True if there are records with detail_fetched = 1.
    """
    conn = _get_connection(db_path)
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM convocatorias WHERE detail_fetched = 1"
        ).fetchone()[0]
        return total > 0
    except Exception:
        return False
    finally:
        conn.close()


def search_convocatorias_local(
    q: str = "",
    page: int = 0,
    page_size: int = 20,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    tipo_administracion: str | None = None,
    regiones: str | None = None,
    orden: str | None = None,
    estado: str | None = None,
    tipos_beneficiario: str | None = None,
    instrumentos: str | None = None,
    finalidad: int | None = None,
    descripcion_finalidad: str | None = None,
    region_desc: str | None = None,
    db_path: str | None = None,
) -> dict:
    """Search convocatorias from local SQLite with filters.

    Only searches records with detail_fetched = 1.

    Args:
        q: Text search query (uses FTS5).
        page: Page number (0-indexed).
        page_size: Results per page.
        fecha_desde: Start date filter (ISO YYYY-MM-DD).
        fecha_hasta: End date filter (ISO YYYY-MM-DD).
        tipo_administracion: Admin type: C (central), A (autonomica), L (local).
        regiones: Comma-separated region IDs.
        orden: Sort direction: asc or desc.
        estado: Status filter: abiertas or cerradas.
        tipos_beneficiario: Comma-separated beneficiary type IDs.
        instrumentos: Comma-separated instrument type IDs.
        finalidad: Purpose/theme ID.
        descripcion_finalidad: Theme description text filter.
        region_desc: Region description text filter.
        db_path: Override path (useful for tests).

    Returns:
        Dict in BDNS Page format: {content, totalElements, totalPages, number, size}.
    """
    conn = _get_connection(db_path)
    try:
        where_parts: list[str] = ["c.detail_fetched = 1"]
        params: list = []

        # Text search via FTS5
        if q and q.strip():
            fts_query = _build_fts_query(q)
            if fts_query:
                where_parts.append(
                    "c.id IN (SELECT rowid FROM convocatorias_fts WHERE convocatorias_fts MATCH ?)"
                )
                params.append(fts_query)

        # Date range
        if fecha_desde:
            where_parts.append("c.fecha_recepcion >= ?")
            params.append(fecha_desde)
        if fecha_hasta:
            where_parts.append("c.fecha_recepcion <= ?")
            params.append(fecha_hasta)

        # Tipo administracion
        if tipo_administracion:
            if tipo_administracion == "C":
                where_parts.append("UPPER(c.nivel1) = 'ESTADO'")
            elif tipo_administracion == "A":
                placeholders = ", ".join("?" for _ in _COMUNIDADES_AUTONOMAS)
                where_parts.append(f"UPPER(c.nivel1) IN ({placeholders})")
                params.extend(sorted(_COMUNIDADES_AUTONOMAS))
            elif tipo_administracion == "L":
                # Local = not central and not autonomica
                placeholders = ", ".join("?" for _ in _COMUNIDADES_AUTONOMAS)
                where_parts.append(f"UPPER(c.nivel1) != 'ESTADO' AND UPPER(c.nivel1) NOT IN ({placeholders})")
                params.extend(sorted(_COMUNIDADES_AUTONOMAS))

        # Regiones filter (JSON array)
        if regiones:
            region_ids = [r.strip() for r in regiones.split(",") if r.strip()]
            if region_ids:
                region_conditions = []
                for rid in region_ids:
                    region_conditions.append(
                        "EXISTS (SELECT 1 FROM json_each(c.regiones_json) "
                        "WHERE json_extract(value, '$.id') = ?)"
                    )
                    params.append(int(rid))
                where_parts.append(f"({' OR '.join(region_conditions)})")

        # Instrumentos filter (JSON array)
        if instrumentos:
            instr_ids = [i.strip() for i in instrumentos.split(",") if i.strip()]
            if instr_ids:
                instr_conditions = []
                for iid in instr_ids:
                    instr_conditions.append(
                        "EXISTS (SELECT 1 FROM json_each(c.instrumentos_json) "
                        "WHERE json_extract(value, '$.id') = ?)"
                    )
                    params.append(int(iid))
                where_parts.append(f"({' OR '.join(instr_conditions)})")

        # Tipos beneficiario filter (JSON array)
        if tipos_beneficiario:
            tb_ids = [t.strip() for t in tipos_beneficiario.split(",") if t.strip()]
            if tb_ids:
                tb_conditions = []
                for tid in tb_ids:
                    tb_conditions.append(
                        "EXISTS (SELECT 1 FROM json_each(c.tipos_beneficiarios_json) "
                        "WHERE json_extract(value, '$.id') = ?)"
                    )
                    params.append(int(tid))
                where_parts.append(f"({' OR '.join(tb_conditions)})")

        # Finalidad (direct comparison)
        if finalidad is not None:
            where_parts.append("c.finalidad_id = ?")
            params.append(finalidad)

        # Finalidad by description text (used by analytics drill-down)
        if descripcion_finalidad:
            where_parts.append("c.descripcion_finalidad = ?")
            params.append(descripcion_finalidad)

        # Region by description text (used by analytics drill-down)
        if region_desc:
            where_parts.append(
                "EXISTS (SELECT 1 FROM json_each(c.regiones_json) "
                "WHERE json_extract(value, '$.descripcion') = ?)"
            )
            params.append(region_desc)

        # Estado filter (date-based: unknown status treated as open)
        if estado == "abiertas":
            # Include everything except definitely closed (past end date)
            where_parts.append(
                "NOT (c.fecha_fin_solicitud IS NOT NULL"
                " AND c.fecha_fin_solicitud < date('now'))"
            )
        elif estado == "cerradas":
            # Only grants with end date in the past
            where_parts.append(
                "c.fecha_fin_solicitud IS NOT NULL"
                " AND c.fecha_fin_solicitud < date('now')"
            )

        where_clause = " AND ".join(where_parts)

        # Count total matching
        count_sql = f"SELECT COUNT(*) FROM convocatorias c WHERE {where_clause}"
        total = conn.execute(count_sql, params).fetchone()[0]

        if total == 0:
            return _empty_response(page, page_size)

        total_pages = max(1, (total + page_size - 1) // page_size)

        # Sort
        order_dir = "ASC" if orden == "asc" else "DESC"
        order_clause = f"c.fecha_recepcion {order_dir}"

        # Fetch page
        offset = page * page_size
        data_sql = f"""
            SELECT c.numero_convocatoria, c.descripcion, c.descripcion_leng,
                   c.fecha_recepcion, c.nivel1, c.nivel2, c.nivel3,
                   c.presupuesto_total, c.abierto,
                   c.fecha_inicio_solicitud, c.fecha_fin_solicitud,
                   c.text_inicio, c.text_fin
            FROM convocatorias c
            WHERE {where_clause}
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(data_sql, [*params, page_size, offset]).fetchall()

        content = [_row_to_search_result(row) for row in rows]

        return {
            "content": content,
            "totalElements": total,
            "totalPages": total_pages,
            "number": page,
            "size": page_size,
        }
    finally:
        conn.close()


async def search_convocatorias_local_async(
    q: str = "",
    page: int = 0,
    page_size: int = 20,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    tipo_administracion: str | None = None,
    regiones: str | None = None,
    orden: str | None = None,
    estado: str | None = None,
    tipos_beneficiario: str | None = None,
    instrumentos: str | None = None,
    finalidad: int | None = None,
    descripcion_finalidad: str | None = None,
    region_desc: str | None = None,
    db_path: str | None = None,
) -> dict:
    """Async wrapper for search_convocatorias_local."""
    return await asyncio.to_thread(
        search_convocatorias_local,
        q, page, page_size, fecha_desde, fecha_hasta,
        tipo_administracion, regiones, orden, estado,
        tipos_beneficiario, instrumentos, finalidad,
        descripcion_finalidad, region_desc, db_path,
    )


def get_latest_convocatorias_local(
    page: int = 0,
    page_size: int = 20,
    db_path: str | None = None,
) -> dict:
    """Get latest convocatorias from local SQLite.

    Args:
        page: Page number (0-indexed).
        page_size: Results per page.
        db_path: Override path (useful for tests).

    Returns:
        Dict in BDNS Page format.
    """
    conn = _get_connection(db_path)
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM convocatorias WHERE detail_fetched = 1"
        ).fetchone()[0]

        if total == 0:
            return _empty_response(page, page_size)

        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = page * page_size

        rows = conn.execute(
            """SELECT numero_convocatoria, descripcion, descripcion_leng,
                      fecha_recepcion, nivel1, nivel2, nivel3,
                      presupuesto_total, abierto,
                      fecha_inicio_solicitud, fecha_fin_solicitud,
                      text_inicio, text_fin
               FROM convocatorias
               WHERE detail_fetched = 1
               ORDER BY fecha_recepcion DESC
               LIMIT ? OFFSET ?""",
            (page_size, offset),
        ).fetchall()

        content = [_row_to_search_result(row) for row in rows]

        return {
            "content": content,
            "totalElements": total,
            "totalPages": total_pages,
            "number": page,
            "size": page_size,
        }
    finally:
        conn.close()


async def get_latest_convocatorias_local_async(
    page: int = 0,
    page_size: int = 20,
    db_path: str | None = None,
) -> dict:
    """Async wrapper for get_latest_convocatorias_local."""
    return await asyncio.to_thread(
        get_latest_convocatorias_local, page, page_size, db_path,
    )


# --- Analytics queries ---


# Total net tax revenue (recaudación tributaria líquida) by year in euros.
# Source: AEAT — Informes Anuales de Recaudación Tributaria
# https://sede.agenciatributaria.gob.es/Sede/datosabiertos/catalogo/hacienda/Informes_anuales_de_Recaudacion_Tributaria.shtml
TAX_REVENUE_BY_YEAR: dict[str, dict] = {
    "2014": {
        "amount": 174_987_000_000,
        "source_url": "https://sede.agenciatributaria.gob.es/Sede/estadisticas/recaudacion-tributaria/informe-anual/ejercicio-2014/resumen.html",
    },
    "2015": {
        "amount": 182_009_000_000,
        "source_url": "https://sede.agenciatributaria.gob.es/Sede/estadisticas/recaudacion-tributaria/informe-anual/ejercicio-2015/resumen.html",
    },
    "2016": {
        "amount": 186_249_000_000,
        "source_url": "https://sede.agenciatributaria.gob.es/Sede/estadisticas/recaudacion-tributaria/informe-anual/ejercicio-2016/resumen.html",
    },
    "2017": {
        "amount": 193_951_000_000,
        "source_url": "https://sede.agenciatributaria.gob.es/Sede/estadisticas/recaudacion-tributaria/informe-anual/ejercicio-2017/resumen.html",
    },
    "2018": {
        "amount": 208_685_000_000,
        "source_url": "https://sede.agenciatributaria.gob.es/Sede/estadisticas/recaudacion-tributaria/informe-anual/ejercicio-2018/resumen.html",
    },
    "2019": {
        "amount": 212_808_000_000,
        "source_url": "https://sede.agenciatributaria.gob.es/Sede/estadisticas/recaudacion-tributaria/informe-anual/ejercicio-2019/resumen.html",
    },
    "2020": {
        "amount": 194_051_000_000,
        "source_url": "https://sede.agenciatributaria.gob.es/Sede/estadisticas/recaudacion-tributaria/informe-anual/ejercicio-2020/resumen.html",
    },
    "2021": {
        "amount": 223_385_000_000,
        "source_url": "https://sede.agenciatributaria.gob.es/Sede/estadisticas/recaudacion-tributaria/informe-anual/ejercicio-2021/resumen.html",
    },
    "2022": {
        "amount": 255_463_000_000,
        "source_url": "https://sede.agenciatributaria.gob.es/Sede/estadisticas/recaudacion-tributaria/informe-anual/ejercicio-2022/resumen.html",
    },
    "2023": {
        "amount": 271_935_000_000,
        "source_url": "https://sede.agenciatributaria.gob.es/Sede/estadisticas/recaudacion-tributaria/informe-anual/ejercicio-2023/resumen.html",
    },
    "2024": {
        "amount": 294_734_000_000,
        "source_url": "https://sede.agenciatributaria.gob.es/Sede/estadisticas/recaudacion-tributaria/informe-anual/ejercicio-2024/resumen.html",
    },
}


def analytics_by_year(db_path: str | None = None) -> list[dict]:
    """Count convocatorias and sum budget by year.

    Includes tax revenue reference data from AEAT for context.

    Args:
        db_path: Override path (useful for tests).

    Returns:
        List of {label, count, budget, tax_revenue, tax_source_url} sorted by year.
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT strftime('%Y', fecha_recepcion) as year,
                      COUNT(*) as count,
                      COALESCE(SUM(presupuesto_total), 0) as budget
               FROM convocatorias
               WHERE fecha_recepcion IS NOT NULL
               GROUP BY year
               ORDER BY year"""
        ).fetchall()
        result = []
        for row in rows:
            year = row["year"]
            tax_data = TAX_REVENUE_BY_YEAR.get(year)
            result.append({
                "label": year,
                "count": row["count"],
                "budget": row["budget"],
                "tax_revenue": tax_data["amount"] if tax_data else None,
                "tax_source_url": tax_data["source_url"] if tax_data else None,
            })
        return result
    finally:
        conn.close()


def analytics_monthly_trend(
    year: int, db_path: str | None = None
) -> list[dict]:
    """Count convocatorias by month for a given year.

    Args:
        year: Year to filter.
        db_path: Override path (useful for tests).

    Returns:
        List of {label, count, budget} for each month.
    """
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT strftime('%m', fecha_recepcion) as month,
                      COUNT(*) as count,
                      COALESCE(SUM(presupuesto_total), 0) as budget
               FROM convocatorias
               WHERE strftime('%Y', fecha_recepcion) = ?
               GROUP BY month
               ORDER BY month""",
            (str(year),),
        ).fetchall()
        return [{"label": row["month"], "count": row["count"], "budget": row["budget"]} for row in rows]
    finally:
        conn.close()


def analytics_by_theme(
    year_from: int | None = None,
    year_to: int | None = None,
    limit: int = 15,
    db_path: str | None = None,
) -> list[dict]:
    """Count convocatorias by finalidad (theme).

    Args:
        year_from: Optional start year filter.
        year_to: Optional end year filter.
        limit: Max results.
        db_path: Override path (useful for tests).

    Returns:
        List of {label, count, budget} sorted by count desc.
    """
    conn = _get_connection(db_path)
    try:
        where_parts = ["descripcion_finalidad IS NOT NULL"]
        params: list = []

        if year_from:
            where_parts.append("fecha_recepcion >= ?")
            params.append(f"{year_from}-01-01")
        if year_to:
            where_parts.append("fecha_recepcion <= ?")
            params.append(f"{year_to}-12-31")

        where_clause = " AND ".join(where_parts)
        params.append(limit)

        rows = conn.execute(
            f"""SELECT descripcion_finalidad as theme,
                       finalidad_id,
                       COUNT(*) as count,
                       COALESCE(SUM(presupuesto_total), 0) as budget
                FROM convocatorias
                WHERE {where_clause}
                GROUP BY theme
                ORDER BY count DESC
                LIMIT ?""",
            params,
        ).fetchall()
        return [
            {"label": row["theme"], "code": row["finalidad_id"], "count": row["count"], "budget": row["budget"]}
            for row in rows
        ]
    finally:
        conn.close()


def analytics_by_region(
    year_from: int | None = None,
    year_to: int | None = None,
    limit: int = 20,
    db_path: str | None = None,
) -> list[dict]:
    """Count convocatorias by region (parsed from regiones_json).

    Args:
        year_from: Optional start year filter.
        year_to: Optional end year filter.
        limit: Max results.
        db_path: Override path (useful for tests).

    Returns:
        List of {label, count, budget} sorted by count desc.
    """
    conn = _get_connection(db_path)
    try:
        where_parts = ["regiones_json IS NOT NULL"]
        params: list = []

        if year_from:
            where_parts.append("fecha_recepcion >= ?")
            params.append(f"{year_from}-01-01")
        if year_to:
            where_parts.append("fecha_recepcion <= ?")
            params.append(f"{year_to}-12-31")

        where_clause = " AND ".join(where_parts)

        rows = conn.execute(
            f"""SELECT regiones_json, presupuesto_total
                FROM convocatorias
                WHERE {where_clause}""",
            params,
        ).fetchall()

        # Aggregate in Python since regions are JSON arrays
        region_counts: dict[str, dict] = {}
        for row in rows:
            try:
                regions = json.loads(row["regiones_json"])
            except (json.JSONDecodeError, TypeError):
                continue
            budget = row["presupuesto_total"] or 0
            for region in regions:
                if isinstance(region, dict):
                    name = region.get("descripcion", "")
                    code = region.get("codigo", "")
                else:
                    name = str(region)
                    code = ""
                if not name:
                    continue
                if name not in region_counts:
                    region_counts[name] = {"count": 0, "budget": 0, "code": code}
                region_counts[name]["count"] += 1
                region_counts[name]["budget"] += budget

        sorted_regions = sorted(region_counts.items(), key=lambda x: x[1]["count"], reverse=True)
        return [
            {"label": name, "code": data["code"], "count": data["count"], "budget": data["budget"]}
            for name, data in sorted_regions[:limit]
        ]
    finally:
        conn.close()


def analytics_top_organs(
    year_from: int | None = None,
    year_to: int | None = None,
    limit: int = 10,
    db_path: str | None = None,
) -> list[dict]:
    """Top convocantes (organismos) by number of convocatorias.

    Args:
        year_from: Optional start year filter.
        year_to: Optional end year filter.
        limit: Max results.
        db_path: Override path (useful for tests).

    Returns:
        List of {label, sublabel, count, budget} sorted by count desc.
    """
    conn = _get_connection(db_path)
    try:
        where_parts = ["nivel2 IS NOT NULL"]
        params: list = []

        if year_from:
            where_parts.append("fecha_recepcion >= ?")
            params.append(f"{year_from}-01-01")
        if year_to:
            where_parts.append("fecha_recepcion <= ?")
            params.append(f"{year_to}-12-31")

        where_clause = " AND ".join(where_parts)
        params.append(limit)

        rows = conn.execute(
            f"""SELECT nivel1, nivel2,
                       COUNT(*) as count,
                       COALESCE(SUM(presupuesto_total), 0) as budget
                FROM convocatorias
                WHERE {where_clause}
                GROUP BY nivel1, nivel2
                ORDER BY count DESC
                LIMIT ?""",
            params,
        ).fetchall()
        return [
            {
                "label": row["nivel2"],
                "sublabel": row["nivel1"],
                "count": row["count"],
                "budget": row["budget"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def analytics_status(db_path: str | None = None) -> dict:
    """Count open vs closed convocatorias.

    Args:
        db_path: Override path (useful for tests).

    Returns:
        Dict with open and closed counts.
    """
    conn = _get_connection(db_path)
    try:
        row = conn.execute(
            """SELECT
                SUM(CASE WHEN fecha_fin_solicitud IS NOT NULL
                         AND fecha_fin_solicitud < date('now')
                    THEN 1 ELSE 0 END) as closed_count,
                COUNT(*) as total
               FROM convocatorias
               WHERE detail_fetched = 1"""
        ).fetchone()
        total = row["total"] or 0
        closed = row["closed_count"] or 0
        return {
            "open": total - closed,
            "closed": closed,
            "total": total,
        }
    finally:
        conn.close()


def analytics_summary(db_path: str | None = None) -> dict:
    """Get summary statistics.

    Args:
        db_path: Override path (useful for tests).

    Returns:
        Dict with total, total_budget, open_count, avg_budget.
    """
    conn = _get_connection(db_path)
    try:
        row = conn.execute(
            """SELECT
                COUNT(*) as total,
                COALESCE(SUM(presupuesto_total), 0) as total_budget,
                SUM(CASE WHEN fecha_fin_solicitud IS NULL
                         OR fecha_fin_solicitud >= date('now')
                    THEN 1 ELSE 0 END) as open_count,
                COALESCE(AVG(CASE WHEN presupuesto_total > 0 THEN presupuesto_total END), 0) as avg_budget
               FROM convocatorias"""
        ).fetchone()
        return {
            "total": row["total"] or 0,
            "total_budget": row["total_budget"] or 0,
            "open_count": row["open_count"] or 0,
            "avg_budget": row["avg_budget"] or 0,
        }
    finally:
        conn.close()


def aggregate_by_year_for_ids(
    ids: list[int], db_path: str | None = None
) -> list[dict]:
    """Aggregate convocatorias by year for a given set of IDs.

    Uses a temp table to avoid SQLite's 999-variable binding limit.

    Args:
        ids: List of convocatoria primary-key IDs.
        db_path: Override path (useful for tests).

    Returns:
        List of {year, count, budget} dicts sorted by year.
    """
    if not ids:
        return []

    conn = _get_connection(db_path)
    try:
        conn.execute("CREATE TEMP TABLE _trend_ids (id INTEGER PRIMARY KEY)")

        # Insert in batches of 500 to stay under binding limits
        batch_size = 500
        for i in range(0, len(ids), batch_size):
            batch = ids[i : i + batch_size]
            placeholders = ", ".join("(?)" for _ in batch)
            conn.execute(
                f"INSERT OR IGNORE INTO _trend_ids VALUES {placeholders}", batch
            )

        rows = conn.execute(
            """SELECT substr(fecha_recepcion, 1, 4) AS year,
                      COUNT(*) AS count,
                      COALESCE(SUM(presupuesto_total), 0) AS budget
               FROM convocatorias
               WHERE id IN (SELECT id FROM _trend_ids)
                 AND fecha_recepcion IS NOT NULL
               GROUP BY year
               ORDER BY year"""
        ).fetchall()

        return [
            {"year": row["year"], "count": row["count"], "budget": row["budget"]}
            for row in rows
        ]
    finally:
        conn.execute("DROP TABLE IF EXISTS _trend_ids")
        conn.close()


def get_embedding_text(row: dict | sqlite3.Row) -> str:
    """Build the text used for generating an embedding from a convocatoria.

    Args:
        row: Convocatoria data (from SQLite row or dict).

    Returns:
        Concatenated text suitable for embedding.
    """
    parts = []

    desc = row.get("descripcion") if isinstance(row, dict) else row["descripcion"]
    if desc:
        parts.append(desc)

    desc_leng = row.get("descripcion_leng") if isinstance(row, dict) else row["descripcion_leng"]
    if desc_leng:
        parts.append(desc_leng)

    finalidad = row.get("descripcion_finalidad") if isinstance(row, dict) else row["descripcion_finalidad"]
    if finalidad:
        parts.append(f"Finalidad: {finalidad}")

    # Convocante
    n3 = row.get("nivel3") if isinstance(row, dict) else row["nivel3"]
    n2 = row.get("nivel2") if isinstance(row, dict) else row["nivel2"]
    n1 = row.get("nivel1") if isinstance(row, dict) else row["nivel1"]
    organ_parts = [p for p in [n3, n2, n1] if p]
    if organ_parts:
        parts.append(f"Convocante: {' - '.join(organ_parts)}")

    # JSON fields (only available on rows with detail)
    for field_name, label in [
        ("tipos_beneficiarios_json", "Beneficiarios"),
        ("regiones_json", "Regiones"),
        ("instrumentos_json", "Instrumentos"),
        ("sectores_json", "Sectores"),
        ("objetivos_json", "Objetivos"),
    ]:
        raw = row.get(field_name) if isinstance(row, dict) else row[field_name]
        if raw:
            try:
                items = json.loads(raw)
                names = [
                    (i.get("descripcion", "") if isinstance(i, dict) else str(i))
                    for i in items
                ]
                names = [n for n in names if n]
                if names:
                    parts.append(f"{label}: {', '.join(names)}")
            except (json.JSONDecodeError, TypeError):
                pass

    return "\n".join(parts)


def _empty_response(page: int, page_size: int) -> dict:
    """Return an empty paginated response."""
    return {
        "content": [],
        "totalElements": 0,
        "totalPages": 0,
        "number": page,
        "size": page_size,
    }
