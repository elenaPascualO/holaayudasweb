"""Tests for top beneficiaries API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@patch("backend.routes.beneficiarios.has_data", return_value=False)
@patch("backend.routes.beneficiarios.search_top_beneficiaries", new_callable=AsyncMock)
async def test_search_top_beneficiaries_with_year(mock_search, mock_has_data, client):
    """Search endpoint filters by year (BDNS fallback when no local data)."""
    mock_search.return_value = {
        "content": [
            {
                "beneficiario": "ES A07129430 AIR EUROPA LINEAS AEREAS, SA",
                "ayudaETotal": 500000000,
            }
        ],
        "totalElements": 1,
        "totalPages": 1,
        "number": 0,
        "size": 20,
    }
    response = await client.get("/api/beneficiarios-top?anio=2024")
    assert response.status_code == 200
    data = response.json()
    assert len(data["content"]) == 1
    call_params = mock_search.call_args[0][0]
    assert call_params["anios"] == [2024]


@patch("backend.routes.beneficiarios.has_data", return_value=False)
@patch("backend.routes.beneficiarios.search_top_beneficiaries", new_callable=AsyncMock)
async def test_search_top_beneficiaries_with_nifcif(mock_search, mock_has_data, client):
    """Search endpoint filters by NIF/CIF (BDNS fallback when no local data)."""
    mock_search.return_value = {
        "content": [],
        "totalElements": 0,
        "totalPages": 0,
        "number": 0,
        "size": 20,
    }
    response = await client.get("/api/beneficiarios-top?nifCif=A07129430")
    assert response.status_code == 200
    call_params = mock_search.call_args[0][0]
    assert call_params["nifCif"] == "A07129430"


@patch("backend.routes.beneficiarios.has_data", return_value=False)
@patch("backend.routes.beneficiarios.search_top_beneficiaries", new_callable=AsyncMock)
async def test_search_top_beneficiaries_default_sort(mock_search, mock_has_data, client):
    """Search endpoint uses default sort via BDNS when DB is empty."""
    mock_search.return_value = {
        "content": [],
        "totalElements": 0,
        "totalPages": 0,
        "number": 0,
        "size": 20,
    }
    response = await client.get("/api/beneficiarios-top")
    assert response.status_code == 200
    call_params = mock_search.call_args[0][0]
    assert call_params["order"] == "ayudaETotal"
    assert call_params["direccion"] == "desc"


@patch("backend.routes.beneficiarios.has_data", return_value=True)
@patch("backend.routes.beneficiarios.get_top_beneficiarios_aggregated_async", new_callable=AsyncMock)
async def test_no_year_uses_aggregated_sqlite(mock_aggregated, mock_has_data, client):
    """When anio=None and no q, uses aggregated SQLite query."""
    mock_aggregated.return_value = {
        "content": [
            {"idPersona": 1, "beneficiario": "X", "nifCif": "A123", "nombre": "Test", "ayudaETotal": 100},
        ],
        "totalElements": 1,
        "totalPages": 1,
        "number": 0,
        "size": 20,
    }
    response = await client.get("/api/beneficiarios-top")
    assert response.status_code == 200
    mock_aggregated.assert_called_once_with(page=0, page_size=20)


@patch("backend.routes.beneficiarios.has_data", return_value=False)
@patch("backend.routes.beneficiarios.get_top_beneficiaries_years", new_callable=AsyncMock)
async def test_get_years(mock_years, mock_has_data, client):
    """Years endpoint returns list of years (BDNS fallback when no local data)."""
    mock_years.return_value = [2024, 2023, 2022, 2021]
    response = await client.get("/api/beneficiarios-top/anios")
    assert response.status_code == 200
    data = response.json()
    assert data == [2024, 2023, 2022, 2021]
    mock_years.assert_called_once()
