"""Tests for concesiones API endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@patch("backend.routes.concesiones.search_concesiones", new_callable=AsyncMock)
async def test_search_concesiones_by_bdns_code(mock_search, client):
    """Search concesiones by BDNS code returns results."""
    mock_search.return_value = {
        "content": [
            {
                "id": 1,
                "beneficiario": "A12345678 - EMPRESA TEST S.L.",
                "importeConcedido": 50000,
                "fechaConcesion": "15/01/2026",
            }
        ],
        "totalElements": 1,
        "totalPages": 1,
        "number": 0,
        "size": 20,
    }
    response = await client.get("/api/concesiones?bdnsCode=886707")
    assert response.status_code == 200
    data = response.json()
    assert len(data["content"]) == 1
    assert data["content"][0]["importeConcedido"] == 50000
    call_params = mock_search.call_args[0][0]
    assert call_params["bdnsCode"] == "886707"


@patch("backend.routes.concesiones.search_concesiones", new_callable=AsyncMock)
async def test_search_concesiones_by_nif(mock_search, client):
    """Search concesiones by NIF/CIF returns results."""
    mock_search.return_value = {
        "content": [],
        "totalElements": 0,
        "totalPages": 0,
        "number": 0,
        "size": 20,
    }
    response = await client.get("/api/concesiones?nifCif=A12345678")
    assert response.status_code == 200
    call_params = mock_search.call_args[0][0]
    assert call_params["nifCif"] == "A12345678"


@patch("backend.routes.concesiones.search_concesiones", new_callable=AsyncMock)
async def test_search_concesiones_error(mock_search, client):
    """Search concesiones returns error on BDNS failure."""
    from backend.services.bdns_client import BDNSError

    mock_search.side_effect = BDNSError("BDNS API timeout", status_code=504)
    response = await client.get("/api/concesiones?bdnsCode=886707")
    assert response.status_code == 504
