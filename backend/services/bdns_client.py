"""HTTP client for the BDNS (Base de Datos Nacional de Subvenciones) API."""

import asyncio
import hashlib
import json
import logging
from datetime import datetime
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

# Global semaphore to limit concurrent outbound BDNS requests
_global_semaphore = asyncio.Semaphore(5)

# Retry settings for 429 responses
_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 1.0  # seconds

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

    if params.get("orden"):
        bdns_params["order"] = "fechaRecepcion"
        bdns_params["direccion"] = params["orden"]

    if params.get("tiposBeneficiario"):
        bdns_params["tiposBeneficiario"] = params["tiposBeneficiario"]

    if params.get("instrumentos"):
        bdns_params["instrumentos"] = params["instrumentos"]

    if params.get("finalidad") is not None:
        bdns_params["finalidad"] = params["finalidad"]

    return bdns_params


async def _fetch(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    """Make a GET request to the BDNS API with rate limiting and retry.

    Acquires the global semaphore before each request to limit concurrency.
    Retries on 429 (Too Many Requests) with exponential backoff.

    Args:
        endpoint: API path (e.g., "/convocatorias/busqueda").
        params: Query parameters.

    Returns:
        Parsed JSON response.

    Raises:
        BDNSError: On HTTP or connection errors.
    """
    client = await get_client()

    for attempt in range(_MAX_RETRIES + 1):
        async with _global_semaphore:
            try:
                response = await client.get(endpoint, params=params)
                if response.status_code == 429:
                    if attempt < _MAX_RETRIES:
                        delay = _RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            "429 Too Many Requests for %s, retrying in %.1fs (attempt %d/%d)",
                            endpoint, delay, attempt + 1, _MAX_RETRIES,
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.error("429 Too Many Requests for %s after %d retries", endpoint, _MAX_RETRIES)
                    raise BDNSError("BDNS API rate limited", status_code=429)
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


async def search_concesiones(params: dict[str, Any]) -> dict[str, Any]:
    """Search concessions via /concesiones/busqueda.

    Args:
        params: Search parameters (bdnsCode, nifCif, page, pageSize).

    Returns:
        Paginated response with content, totalElements, totalPages, etc.
    """
    bdns_params: dict[str, Any] = {"vpd": BDNS_VPD}

    if params.get("bdnsCode"):
        bdns_params["numeroConvocatoria"] = params["bdnsCode"]

    if params.get("nifCif"):
        bdns_params["nifCif"] = params["nifCif"]

    if params.get("fechaDesde"):
        bdns_params["fechaDesde"] = _convert_date_to_bdns(params["fechaDesde"])

    if params.get("fechaHasta"):
        bdns_params["fechaHasta"] = _convert_date_to_bdns(params["fechaHasta"])

    if params.get("page") is not None:
        bdns_params["page"] = params["page"]

    if params.get("pageSize"):
        bdns_params["pageSize"] = params["pageSize"]

    key = _cache_key("concesiones", bdns_params)

    cached = cache.get(key)
    if cached is not None:
        return cached

    data = await _fetch("/concesiones/busqueda", params=bdns_params)
    cache.set(key, data, CACHE_TTL_SEARCH)
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


async def search_top_beneficiaries(params: dict[str, Any]) -> dict[str, Any]:
    """Search top beneficiaries via /grandesbeneficiarios/busqueda.

    Args:
        params: Search parameters (page, pageSize, order, direccion, anios, nifCif).

    Returns:
        Paginated response with content, totalElements, totalPages, etc.
    """
    bdns_params: dict[str, Any] = {}

    if params.get("page") is not None:
        bdns_params["page"] = params["page"]

    if params.get("pageSize"):
        bdns_params["pageSize"] = params["pageSize"]

    if params.get("order"):
        bdns_params["order"] = params["order"]

    if params.get("direccion"):
        bdns_params["direccion"] = params["direccion"]

    if params.get("anios"):
        bdns_params["anios"] = params["anios"]

    if params.get("nifCif"):
        bdns_params["nifCif"] = params["nifCif"]

    key = _cache_key("top_beneficiaries", bdns_params)

    cached = cache.get(key)
    if cached is not None:
        return cached

    data = await _fetch("/grandesbeneficiarios/busqueda", params=bdns_params)
    cache.set(key, data, CACHE_TTL_DETAIL)
    return data


async def get_top_beneficiaries_years() -> Any:
    """Get available years for top beneficiaries via /grandesbeneficiarios/anios.

    Returns:
        List of available years.
    """
    key = "top_beneficiaries:years"

    cached = cache.get(key)
    if cached is not None:
        return cached

    data = await _fetch("/grandesbeneficiarios/anios")
    cache.set(key, data, CACHE_TTL_CATALOGS)
    return data


def _parse_bdns_date(date_str: str | None) -> datetime | None:
    """Parse a BDNS date string into a datetime.

    Handles both dd/mm/yyyy (BDNS native) and YYYY-MM-DD (ISO) formats,
    mirroring the frontend parseDate() logic.

    Args:
        date_str: Date in dd/mm/yyyy or YYYY-MM-DD format.

    Returns:
        Parsed datetime or None.
    """
    if not date_str:
        return None
    try:
        if "/" in date_str:
            return datetime.strptime(date_str, "%d/%m/%Y")
        if "-" in date_str:
            return datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    return None


def get_grant_status(grant: dict[str, Any]) -> str:
    """Determine the application status of a grant.

    Mirrors the logic in frontend/src/utils/dates.js:getGrantStatus().

    Args:
        grant: Grant detail object from BDNS.

    Returns:
        One of: "open", "closed", "upcoming", "permanent", "unknown".
    """
    if not grant:
        return "unknown"

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Permanently open with no end date
    if grant.get("abierto") is True and not grant.get("fechaFinSolicitud"):
        return "permanent"

    start_date = _parse_bdns_date(
        grant.get("fechaInicioSolicitud") or grant.get("textInicio")
    )
    end_date = _parse_bdns_date(
        grant.get("fechaFinSolicitud") or grant.get("textFin")
    )

    # End date in the past → closed
    if end_date and end_date < today:
        return "closed"

    # Start date in the future → upcoming
    if start_date and start_date > today:
        return "upcoming"

    # End date in the future (start is past or absent) → open
    if end_date and end_date >= today:
        return "open"

    # abierto flag from BDNS
    if grant.get("abierto") is True:
        return "open"

    return "unknown"


# Status groups for filtering
_OPEN_STATUSES = {"open", "upcoming", "permanent", "unknown"}


async def search_convocatorias_enriched(
    params: dict[str, Any], estado: str
) -> dict[str, Any]:
    """Search grants and enrich with detail data, filtering by status.

    Fetches grant details in parallel to determine status, then filters
    results by the requested status group.

    Args:
        params: Search parameters (same as search_convocatorias).
        estado: Status filter — "abiertas" or "cerradas".

    Returns:
        Paginated response with enriched content (_status, _presupuestoTotal).
    """
    desired_page_size = int(params.get("pageSize", 20))
    enriched_results: list[dict[str, Any]] = []
    semaphore = asyncio.Semaphore(5)
    max_extra_pages = 3
    current_page = int(params.get("page", 0))
    total_elements_original = 0

    for attempt in range(1 + max_extra_pages):
        fetch_params = {**params, "page": current_page + attempt, "pageSize": 50}
        search_data = await search_convocatorias(fetch_params)

        if attempt == 0:
            total_elements_original = search_data.get("totalElements", 0)

        items = search_data.get("content", [])
        if not items:
            break

        async def fetch_detail(item: dict[str, Any]) -> dict[str, Any]:
            code = str(item.get("numeroConvocatoria", ""))
            if not code:
                return item
            async with semaphore:
                try:
                    detail = await get_convocatoria_detail(code)
                except BDNSError:
                    return item
            status = get_grant_status(detail)
            enriched = {**item, "_status": status}
            budget = detail.get("presupuestoTotal")
            if budget is not None:
                enriched["_presupuestoTotal"] = budget
            return enriched

        tasks = [fetch_detail(item) for item in items]
        enriched_items = await asyncio.gather(*tasks)

        # Filter by status
        for item in enriched_items:
            item_status = item.get("_status", "unknown")
            if estado == "abiertas" and item_status not in _OPEN_STATUSES:
                continue
            if estado == "cerradas" and item_status != "closed":
                continue
            enriched_results.append(item)

        if len(enriched_results) >= desired_page_size:
            break

    # Trim to requested page size
    page_results = enriched_results[:desired_page_size]

    return {
        "content": page_results,
        "totalElements": total_elements_original,
        "totalPages": max(
            1,
            (total_elements_original + desired_page_size - 1) // desired_page_size,
        ),
        "number": current_page,
        "size": desired_page_size,
    }
