"""Grant (convocatoria) routes."""

from fastapi import APIRouter, HTTPException, Query

from backend.services.bdns_client import (
    BDNSError,
    get_latest_convocatorias,
    get_convocatoria_detail,
    search_convocatorias,
)

router = APIRouter(prefix="/api", tags=["convocatorias"])


@router.get("/convocatorias")
async def search_grants(
    q: str = Query(default="", description="Search text"),
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
) -> dict:
    """Search grants with filters."""
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

    try:
        return await search_convocatorias(params)
    except BDNSError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/convocatorias/ultimas")
async def latest_grants(
    page: int = Query(default=0, ge=0, description="Page number (0-indexed)"),
    pageSize: int = Query(default=20, ge=1, le=50, description="Results per page"),
) -> dict:
    """Get latest published grants."""
    try:
        return await get_latest_convocatorias({"page": page, "pageSize": pageSize})
    except BDNSError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/convocatorias/{bdns_code}")
async def grant_detail(bdns_code: str) -> dict:
    """Get full detail of a specific grant by BDNS code."""
    try:
        return await get_convocatoria_detail(bdns_code)
    except BDNSError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
