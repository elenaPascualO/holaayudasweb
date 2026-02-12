"""Catalog routes (regions, purposes, instruments, activities, beneficiary types)."""

from fastapi import APIRouter, HTTPException

from backend.services.bdns_client import BDNSError, get_catalog

router = APIRouter(prefix="/api/catalogo", tags=["catalogs"])


@router.get("/regiones")
async def get_regions():
    """Get regions catalog (hierarchical NUTS tree)."""
    try:
        return await get_catalog("regiones")
    except BDNSError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/finalidades")
async def get_purposes():
    """Get spending purposes catalog."""
    try:
        return await get_catalog("finalidades")
    except BDNSError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/instrumentos")
async def get_instruments():
    """Get aid instrument types catalog."""
    try:
        return await get_catalog("instrumentos")
    except BDNSError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/actividades")
async def get_activities():
    """Get NACE activity sectors catalog."""
    try:
        return await get_catalog("actividades")
    except BDNSError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/beneficiarios")
async def get_beneficiary_types():
    """Get beneficiary types catalog."""
    try:
        return await get_catalog("beneficiarios")
    except BDNSError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
