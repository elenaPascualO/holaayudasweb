"""HTTP client for the BDNS (Base de Datos Nacional de Subvenciones) API."""

import hashlib
import json
import logging
from typing import Any

import httpx

from backend.config import (
    BDNS_BASE_URL,
    BDNS_TIMEOUT,
    BDNS_VPD,
    CACHE_TTL_CATALOGS,
    CACHE_TTL_DETAIL,
    CACHE_TTL_SEARCH,
)
from backend.services.cache import cache

logger = logging.getLogger(__name__)

# Shared async client (created lazily)
_client: httpx.AsyncClient | None = None

# Catalogs that require vpd parameter
CATALOGS_WITH_VPD = {"finalidades", "beneficiarios"}


class BDNSError(Exception):
    """Error from the BDNS upstream API."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def get_client() -> httpx.AsyncClient:
    """Get or create the shared httpx async client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=BDNS_BASE_URL,
            timeout=BDNS_TIMEOUT,
            headers={"Accept": "application/json"},
        )
    return _client


async def close_client() -> None:
    """Close the httpx client gracefully."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


def _cache_key(prefix: str, params: dict[str, Any]) -> str:
    """Generate a deterministic cache key from prefix and sorted params."""
    sorted_params = json.dumps(params, sort_keys=True, default=str)
    param_hash = hashlib.md5(sorted_params.encode()).hexdigest()[:12]
    return f"{prefix}:{param_hash}"


def _convert_date_to_bdns(iso_date: str) -> str:
    """Convert ISO date (YYYY-MM-DD) to BDNS format (dd/mm/yyyy).

    Args:
        iso_date: Date string in YYYY-MM-DD format.

    Returns:
        Date string in dd/mm/yyyy format.
    """
    parts = iso_date.split("-")
    if len(parts) != 3:
        return iso_date
    return f"{parts[2]}/{parts[1]}/{parts[0]}"


def _build_search_params(params: dict[str, Any]) -> dict[str, Any]:
    """Build query parameters for BDNS search endpoints.

    Converts our API parameter names to BDNS parameter names,
    adds vpd, and converts dates.
    """
    bdns_params: dict[str, Any] = {"vpd": BDNS_VPD}

    if params.get("q"):
        bdns_params["descripcion"] = params["q"]
        bdns_params["descripcionTipoBusqueda"] = 2  # any word

    if params.get("page") is not None:
        bdns_params["page"] = params["page"]

    if params.get("pageSize"):
        bdns_params["pageSize"] = params["pageSize"]

    if params.get("fechaDesde"):
        bdns_params["fechaDesde"] = _convert_date_to_bdns(params["fechaDesde"])

    if params.get("fechaHasta"):
        bdns_params["fechaHasta"] = _convert_date_to_bdns(params["fechaHasta"])

    if params.get("tipoAdministracion"):
        bdns_params["tipoAdministracion"] = params["tipoAdministracion"]

    if params.get("regiones"):
        bdns_params["regiones"] = params["regiones"]

    return bdns_params


async def _fetch(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    """Make a GET request to the BDNS API.

    Args:
        endpoint: API path (e.g., "/convocatorias/busqueda").
        params: Query parameters.

    Returns:
        Parsed JSON response.

    Raises:
        BDNSError: On HTTP or connection errors.
    """
    client = await get_client()
    try:
        response = await client.get(endpoint, params=params)
        if response.status_code == 404:
            raise BDNSError("Resource not found", status_code=404)
        if response.status_code == 400:
            raise BDNSError("Invalid request parameters", status_code=400)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        logger.error("Timeout fetching %s", endpoint)
        raise BDNSError("BDNS API timeout", status_code=504)
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error %s fetching %s", e.response.status_code, endpoint)
        raise BDNSError(f"BDNS API error: {e.response.status_code}", status_code=502)
    except httpx.HTTPError as e:
        logger.error("Connection error fetching %s: %s", endpoint, str(e))
        raise BDNSError("Cannot connect to BDNS API", status_code=502)


async def search_convocatorias(params: dict[str, Any]) -> dict[str, Any]:
    """Search grants via /convocatorias/busqueda.

    Args:
        params: Search parameters (q, page, pageSize, fechaDesde, fechaHasta,
                tipoAdministracion, regiones).

    Returns:
        Paginated response with content, totalElements, totalPages, etc.
    """
    bdns_params = _build_search_params(params)
    key = _cache_key("search", bdns_params)

    cached = cache.get(key)
    if cached is not None:
        return cached

    data = await _fetch("/convocatorias/busqueda", params=bdns_params)
    cache.set(key, data, CACHE_TTL_SEARCH)
    return data


async def get_latest_convocatorias(params: dict[str, Any]) -> dict[str, Any]:
    """Get latest published grants via /convocatorias/ultimas.

    Args:
        params: Pagination parameters (page, pageSize).

    Returns:
        Paginated response with latest grants.
    """
    bdns_params: dict[str, Any] = {"vpd": BDNS_VPD}

    if params.get("page") is not None:
        bdns_params["page"] = params["page"]
    if params.get("pageSize"):
        bdns_params["pageSize"] = params["pageSize"]

    key = _cache_key("latest", bdns_params)

    cached = cache.get(key)
    if cached is not None:
        return cached

    data = await _fetch("/convocatorias/ultimas", params=bdns_params)
    cache.set(key, data, CACHE_TTL_SEARCH)
    return data


async def get_convocatoria_detail(bdns_code: str) -> dict[str, Any]:
    """Get full detail of a specific grant.

    Args:
        bdns_code: The BDNS code (e.g., "886707").

    Returns:
        Full grant detail object.
    """
    key = f"detail:{bdns_code}"

    cached = cache.get(key)
    if cached is not None:
        return cached

    data = await _fetch("/convocatorias", params={"vpd": BDNS_VPD, "numConv": bdns_code})
    cache.set(key, data, CACHE_TTL_DETAIL)
    return data


async def get_catalog(catalog_name: str) -> Any:
    """Get a reference catalog (regions, purposes, instruments, etc.).

    Args:
        catalog_name: One of: regiones, finalidades, instrumentos,
                      actividades, beneficiarios.

    Returns:
        Catalog data (usually a list or tree structure).
    """
    key = f"catalog:{catalog_name}"

    cached = cache.get(key)
    if cached is not None:
        return cached

    params: dict[str, str] = {}
    if catalog_name in CATALOGS_WITH_VPD:
        params["vpd"] = BDNS_VPD

    data = await _fetch(f"/{catalog_name}", params=params or None)
    cache.set(key, data, CACHE_TTL_CATALOGS)
    return data
