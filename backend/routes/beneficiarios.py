"""Top beneficiaries (grandes beneficiarios) routes."""

from fastapi import APIRouter, HTTPException, Query

from backend.services.bdns_client import (
    BDNSError,
    get_top_beneficiaries_years,
    search_top_beneficiaries,
)
from backend.services.beneficiarios_db import (
    get_top_beneficiarios_aggregated_async,
    has_data,
    search_beneficiarios_async,
)

router = APIRouter(prefix="/api", tags=["beneficiarios"])


@router.get("/beneficiarios-top")
async def get_top_beneficiaries(
    page: int = Query(default=0, ge=0, description="Page number (0-indexed)"),
    pageSize: int = Query(default=20, ge=1, le=50, description="Results per page"),
    order: str = Query(default="ayudaETotal", description="Sort field"),
    direccion: str = Query(default="desc", description="Sort direction (asc/desc)"),
    anio: int | None = Query(default=None, description="Year filter"),
    nifCif: str | None = Query(default=None, description="Beneficiary NIF/CIF"),
    q: str | None = Query(default=None, description="Text search (name)"),
) -> dict:
    """Search top beneficiaries with filters.

    Routing logic:
    1. If `q` is provided → SQLite FTS5 search (aggregated when anio=None).
    2. If anio=None, no nifCif, and DB has data → aggregated SQLite query.
    3. Otherwise → proxy to BDNS API.
    """
    # Path 1: Text search via SQLite FTS5
    if q and q.strip():
        if not has_data():
            raise HTTPException(
                status_code=503,
                detail="La base de datos de beneficiarios aun no ha sido sincronizada. Intentalo mas tarde.",
            )
        return await search_beneficiarios_async(
            q=q.strip(),
            anio=anio,
            page=page,
            page_size=pageSize,
        )

    # Path 2: No year + no nifCif + DB has data → aggregated from SQLite
    if anio is None and not nifCif and has_data():
        return await get_top_beneficiarios_aggregated_async(
            page=page,
            page_size=pageSize,
        )

    # Path 3: Specific year or nifCif → proxy to BDNS
    params: dict = {
        "page": page,
        "pageSize": pageSize,
        "order": order,
        "direccion": direccion,
    }
    if anio is not None:
        params["anios"] = [anio]
    if nifCif:
        params["nifCif"] = nifCif

    try:
        return await search_top_beneficiaries(params)
    except BDNSError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/beneficiarios-top/anios")
async def get_years() -> list:
    """Get available years for top beneficiaries."""
    try:
        return await get_top_beneficiaries_years()
    except BDNSError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
