"""Tests for catalog API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@patch("backend.routes.catalogs.get_catalog", new_callable=AsyncMock)
async def test_get_regions(mock_catalog, client):
    """Regions endpoint returns hierarchical data."""
    mock_catalog.return_value = [
        {"id": 1, "descripcion": "España", "children": []}
    ]
    response = await client.get("/api/catalogo/regiones")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["descripcion"] == "España"
    mock_catalog.assert_called_once_with("regiones")


@patch("backend.routes.catalogs.get_catalog", new_callable=AsyncMock)
async def test_get_purposes(mock_catalog, client):
    """Purposes endpoint returns list of purposes."""
    mock_catalog.return_value = [
        {"id": 1, "descripcion": "Educacion"},
        {"id": 2, "descripcion": "Cultura"},
    ]
    response = await client.get("/api/catalogo/finalidades")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    mock_catalog.assert_called_once_with("finalidades")


@patch("backend.routes.catalogs.get_catalog", new_callable=AsyncMock)
async def test_get_instruments(mock_catalog, client):
    """Instruments endpoint returns instrument types."""
    mock_catalog.return_value = [
        {"id": 1, "descripcion": "Subvencion"},
    ]
    response = await client.get("/api/catalogo/instrumentos")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    mock_catalog.assert_called_once_with("instrumentos")


@patch("backend.routes.catalogs.get_catalog", new_callable=AsyncMock)
async def test_get_beneficiary_types(mock_catalog, client):
    """Beneficiary types endpoint returns list."""
    mock_catalog.return_value = [
        {"id": 1, "descripcion": "Persona fisica"},
        {"id": 2, "descripcion": "PYME"},
    ]
    response = await client.get("/api/catalogo/beneficiarios")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    mock_catalog.assert_called_once_with("beneficiarios")


@patch("backend.routes.catalogs.get_catalog", new_callable=AsyncMock)
async def test_catalog_error_handling(mock_catalog, client):
    """Catalog endpoint handles BDNS errors."""
    from backend.services.bdns_client import BDNSError

    mock_catalog.side_effect = BDNSError("Cannot connect", status_code=502)
    response = await client.get("/api/catalogo/regiones")
    assert response.status_code == 502
