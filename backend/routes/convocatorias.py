"""Grant (convocatoria) routes."""

import logging
import time

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from backend.services.bdns_client import (
    BDNSError,
    get_client,
    get_latest_convocatorias,
    get_convocatoria_detail,
    search_convocatorias,
    search_convocatorias_enriched,
)
from backend.services.convocatorias_db import (
    get_convocatoria_detail_local,
    get_latest_convocatorias_local_async,
    has_convocatorias_data,
    search_convocatorias_local_async,
)
from backend.services.rate_limiter import get_client_ip, search_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["convocatorias"])

# Content types that browsers can display inline
_VIEWABLE_TYPES = {
    "application/pdf",
    "text/html",
    "text/plain",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/svg+xml",
}


@router.get("/convocatorias")
async def search_grants(
    request: Request,
    q: str = Query(default="", max_length=500, description="Search text"),
    page: int = Query(default=0, ge=0, description="Page number (0-indexed)"),
    pageSize: int = Query(default=20, ge=1, le=50, description="Results per page"),
    fechaDesde: str | None = Query(default=None, description="Start date (YYYY-MM-DD)"),
    fechaHasta: str | None = Query(default=None, description="End date (YYYY-MM-DD)"),
    tipoAdministracion: str | None = Query(
        default=None, description="Admin type: C, A, L, or O"
    ),
    regiones: str | None = Query(
        default=None, description="Region IDs, comma-separated"
    ),
    orden: str | None = Query(
        default=None, description="Sort direction: asc or desc"
    ),
    estado: str | None = Query(
        default=None, description="Status filter: abiertas or cerradas"
    ),
    tiposBeneficiario: str | None = Query(
        default=None, description="Beneficiary type IDs, comma-separated"
    ),
    instrumentos: str | None = Query(
        default=None, description="Instrument type IDs, comma-separated"
    ),
    finalidad: int | None = Query(
        default=None, description="Purpose/theme ID"
    ),
    descripcionFinalidad: str | None = Query(
        default=None, description="Theme description text filter"
    ),
    regionDesc: str | None = Query(
        default=None, description="Region description text filter"
    ),
) -> dict:
    """Search grants with filters. Uses local SQLite first, falls back to BDNS."""
    search_limiter.check(get_client_ip(request))
    t0 = time.monotonic()
    # Try local SQLite first
    if has_convocatorias_data():
        try:
            result = await search_convocatorias_local_async(
                q=q,
                page=page,
                page_size=pageSize,
                fecha_desde=fechaDesde,
                fecha_hasta=fechaHasta,
                tipo_administracion=tipoAdministracion,
                regiones=regiones,
                orden=orden,
                estado=estado,
                tipos_beneficiario=tiposBeneficiario,
                instrumentos=instrumentos,
                finalidad=finalidad,
                descripcion_finalidad=descripcionFinalidad,
                region_desc=regionDesc,
            )
            elapsed = time.monotonic() - t0
            if elapsed > 0.5:
                logger.warning(
                    "Slow local search: %.2fs (q=%r, estado=%s, desde=%s, hasta=%s)",
                    elapsed, q, estado, fechaDesde, fechaHasta,
                )
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception:
            logger.warning("Local search failed, falling back to BDNS proxy")

    # Fallback to BDNS proxy
    params = {
        "q": q,
        "page": page,
        "pageSize": pageSize,
    }
    if fechaDesde:
        params["fechaDesde"] = fechaDesde
    if fechaHasta:
        params["fechaHasta"] = fechaHasta
    if tipoAdministracion:
        params["tipoAdministracion"] = tipoAdministracion
    if regiones:
        params["regiones"] = regiones
    if orden:
        params["orden"] = orden
    if tiposBeneficiario:
        params["tiposBeneficiario"] = tiposBeneficiario
    if instrumentos:
        params["instrumentos"] = instrumentos
    if finalidad is not None:
        params["finalidad"] = finalidad

    try:
        if estado in ("abiertas", "cerradas"):
            return await search_convocatorias_enriched(params, estado)
        return await search_convocatorias(params)
    except BDNSError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/convocatorias/ultimas")
async def latest_grants(
    page: int = Query(default=0, ge=0, description="Page number (0-indexed)"),
    pageSize: int = Query(default=20, ge=1, le=50, description="Results per page"),
) -> dict:
    """Get latest published grants. Uses local SQLite first, falls back to BDNS."""
    # Try local SQLite first
    if has_convocatorias_data():
        try:
            return await get_latest_convocatorias_local_async(page=page, page_size=pageSize)
        except Exception:
            logger.warning("Local latest query failed, falling back to BDNS proxy")

    # Fallback to BDNS proxy
    try:
        return await get_latest_convocatorias({"page": page, "pageSize": pageSize})
    except BDNSError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/documentos/{doc_id}")
async def get_document(doc_id: str) -> StreamingResponse:
    """Proxy a BDNS document, changing Content-Disposition to inline for viewable types.

    This lets the browser open PDFs and images in its built-in viewer
    instead of forcing a download.
    """
    import io

    client = await get_client()
    try:
        response = await client.get(
            "/convocatorias/documentos",
            params={"idDocumento": doc_id},
        )
        response.raise_for_status()
    except Exception:
        raise HTTPException(status_code=502, detail="Error fetching document from BDNS")

    content_type = response.headers.get("content-type", "application/octet-stream")
    # Extract the base MIME type (ignore charset etc.)
    base_type = content_type.split(";")[0].strip().lower()

    # BDNS sometimes returns application/octet-stream for PDFs — detect via magic bytes
    if base_type == "application/octet-stream" and response.content[:5] == b"%PDF-":
        content_type = "application/pdf"
        base_type = "application/pdf"

    headers: dict[str, str] = {}

    # Copy original content-disposition if present
    original_disposition = response.headers.get("content-disposition", "")

    if base_type in _VIEWABLE_TYPES:
        # Force inline so the browser displays it in its built-in viewer
        headers["Content-Disposition"] = "inline"
    elif original_disposition:
        headers["Content-Disposition"] = original_disposition

    return StreamingResponse(
        io.BytesIO(response.content),
        media_type=content_type,
        headers=headers,
    )


@router.get("/convocatorias/{bdns_code}")
async def grant_detail(bdns_code: str) -> dict:
    """Get full detail of a specific grant by BDNS code.

    Tries local SQLite first (fast, no API call), falls back to BDNS proxy.
    """
    # Try local SQLite first
    try:
        local = get_convocatoria_detail_local(bdns_code)
        if local is not None:
            return local
    except Exception:
        logger.warning("SQLite detail lookup failed for %s, falling back to BDNS", bdns_code)

    # Fallback to BDNS API proxy
    try:
        return await get_convocatoria_detail(bdns_code)
    except BDNSError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
