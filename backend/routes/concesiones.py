"""Concession (concesion) routes."""

from fastapi import APIRouter, HTTPException, Query

from backend.services.bdns_client import BDNSError, search_concesiones

router = APIRouter(prefix="/api", tags=["concesiones"])


@router.get("/concesiones")
async def search_concessions(
    bdnsCode: str | None = Query(
        default=None, description="BDNS convocatoria code"
    ),
    nifCif: str | None = Query(
        default=None, description="Beneficiary NIF/CIF"
    ),
    fechaDesde: str | None = Query(
        default=None, description="Start date (YYYY-MM-DD)"
    ),
    fechaHasta: str | None = Query(
        default=None, description="End date (YYYY-MM-DD)"
    ),
    order: str | None = Query(
        default=None, description="Sort field (e.g. importe, fechaConcesion)"
    ),
    direccion: str | None = Query(
        default=None, description="Sort direction: asc or desc"
    ),
    page: int = Query(default=0, ge=0, description="Page number (0-indexed)"),
    pageSize: int = Query(default=20, ge=1, le=50, description="Results per page"),
) -> dict:
    """Search concessions with filters."""
    params = {
        "page": page,
        "pageSize": pageSize,
    }
    if bdnsCode:
        params["bdnsCode"] = bdnsCode
    if nifCif:
        params["nifCif"] = nifCif
    if fechaDesde:
        params["fechaDesde"] = fechaDesde
    if fechaHasta:
        params["fechaHasta"] = fechaHasta
    if order:
        params["order"] = order
    if direccion:
        params["direccion"] = direccion

    try:
        return await search_concesiones(params)
    except BDNSError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
