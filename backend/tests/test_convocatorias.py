"""Tests for convocatoria API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_health_check(client):
    """Health check returns ok."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "holaayudas-api"


@patch("backend.routes.convocatorias.search_convocatorias", new_callable=AsyncMock)
async def test_search_grants(mock_search, client):
    """Search endpoint returns paginated results."""
    mock_search.return_value = {
        "content": [
            {
                "id": 1,
                "numeroConvocatoria": "886707",
                "descripcion": "Test grant",
                "fechaRecepcion": "2026-01-15",
                "nivel1": "AUTONOMICA",
                "nivel2": "Junta de Andalucia",
            }
        ],
        "totalElements": 1,
        "totalPages": 1,
        "number": 0,
        "size": 20,
    }
    response = await client.get("/api/convocatorias?q=test&page=0&pageSize=20")
    assert response.status_code == 200
    data = response.json()
    assert len(data["content"]) == 1
    assert data["totalElements"] == 1
    mock_search.assert_called_once()


@patch("backend.routes.convocatorias.get_latest_convocatorias", new_callable=AsyncMock)
async def test_latest_grants(mock_latest, client):
    """Latest endpoint returns paginated results."""
    mock_latest.return_value = {
        "content": [{"id": 1, "descripcion": "Latest grant"}],
        "totalElements": 100,
        "totalPages": 5,
        "number": 0,
        "size": 20,
    }
    response = await client.get("/api/convocatorias/ultimas")
    assert response.status_code == 200
    data = response.json()
    assert len(data["content"]) == 1
    mock_latest.assert_called_once()


@patch("backend.routes.convocatorias.get_convocatoria_detail", new_callable=AsyncMock)
async def test_grant_detail(mock_detail, client):
    """Detail endpoint returns grant detail."""
    mock_detail.return_value = {
        "codigoBDNS": "886707",
        "descripcion": "Detailed grant info",
        "presupuestoTotal": 500000,
        "abierto": True,
    }
    response = await client.get("/api/convocatorias/886707")
    assert response.status_code == 200
    data = response.json()
    assert data["codigoBDNS"] == "886707"
    assert data["presupuestoTotal"] == 500000
    mock_detail.assert_called_once_with("886707")


@patch("backend.routes.convocatorias.search_convocatorias", new_callable=AsyncMock)
async def test_search_grants_advanced_filters(mock_search, client):
    """Search endpoint forwards advanced filter params."""
    mock_search.return_value = {
        "content": [],
        "totalElements": 0,
        "totalPages": 0,
        "number": 0,
        "size": 20,
    }
    response = await client.get(
        "/api/convocatorias?q=test&instrumentos=1,2&tiposBeneficiario=3&finalidad=5"
    )
    assert response.status_code == 200
    call_params = mock_search.call_args[0][0]
    assert call_params["instrumentos"] == "1,2"
    assert call_params["tiposBeneficiario"] == "3"
    assert call_params["finalidad"] == 5


@patch("backend.routes.convocatorias.get_convocatoria_detail", new_callable=AsyncMock)
async def test_grant_detail_not_found(mock_detail, client):
    """Detail endpoint returns 404 when grant not found."""
    from backend.services.bdns_client import BDNSError

    mock_detail.side_effect = BDNSError("Resource not found", status_code=404)
    response = await client.get("/api/convocatorias/999999")
    assert response.status_code == 404
