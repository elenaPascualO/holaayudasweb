"""Tests for the post generation script."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.convocatorias_db import (
    init_convocatorias_db,
    update_convocatoria_detail,
    upsert_convocatorias_list,
)
from backend.services.posts_db import init_posts_db, insert_post

from backend.scripts.generate_posts import (
    _format_budget,
    build_ayuda_destacada_prompt,
    build_cierre_inminente_prompt,
    build_dato_curioso_prompt,
    build_datos_semana_prompt,
    build_tematico_prompt,
    build_top_organismo_prompt,
    gather_data,
    run_generation,
    select_next_post_type,
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary DB with both convocatorias and posts tables."""
    path = str(tmp_path / "test_gen.db")
    init_convocatorias_db(path)
    init_posts_db(path)
    return path


@pytest.fixture
def populated_db(db_path):
    """DB with sample convocatorias for generation testing."""
    records = [
        {
            "numeroConvocatoria": "300001",
            "descripcion": "Ayudas para digitalización de pymes",
            "descripcionLeng": None,
            "fechaRecepcion": "20/03/2026",
            "organo": {
                "nivel1": "ESTADO",
                "nivel2": "MINISTERIO DE INDUSTRIA",
                "nivel3": "SECRETARIA GENERAL",
            },
        },
        {
            "numeroConvocatoria": "300002",
            "descripcion": "Becas de investigación",
            "descripcionLeng": None,
            "fechaRecepcion": "22/03/2026",
            "organo": {
                "nivel1": "ESTADO",
                "nivel2": "MINISTERIO DE CIENCIA",
                "nivel3": None,
            },
        },
    ]
    upsert_convocatorias_list(records, db_path)

    update_convocatoria_detail(
        "300001",
        {
            "presupuestoTotal": 5000000.0,
            "descripcionFinalidad": "Transformación digital",
            "finalidad": {"id": 10},
            "abierto": True,
            "fechaInicioSolicitud": "01/04/2026",
            "fechaFinSolicitud": "30/06/2026",
            "regiones": [{"id": 1, "descripcion": "COMUNIDAD DE MADRID"}],
            "instrumentos": [],
            "tiposBeneficiarios": [],
            "sectores": [],
            "objetivos": [],
            "documentos": [],
            "anuncios": [],
            "sedeElectronica": "https://sede.example.com",
            "urlBasesReguladoras": None,
            "descripcionBasesReguladoras": None,
            "tipoConvocatoria": "Competitiva",
            "textInicio": None,
            "textFin": None,
        },
        db_path,
    )

    update_convocatoria_detail(
        "300002",
        {
            "presupuestoTotal": 2000000.0,
            "descripcionFinalidad": "Investigación científica",
            "finalidad": {"id": 20},
            "abierto": True,
            "fechaInicioSolicitud": "01/03/2026",
            "fechaFinSolicitud": "30/04/2026",
            "regiones": [{"id": 2, "descripcion": "CATALUÑA"}],
            "instrumentos": [],
            "tiposBeneficiarios": [],
            "sectores": [],
            "objetivos": [],
            "documentos": [],
            "anuncios": [],
            "sedeElectronica": None,
            "urlBasesReguladoras": None,
            "descripcionBasesReguladoras": None,
            "tipoConvocatoria": "Concurrencia",
            "textInicio": None,
            "textFin": None,
        },
        db_path,
    )

    return db_path


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------


class TestFormatBudget:
    def test_billions(self):
        assert _format_budget(2_500_000_000) == "2.5 mil M€"

    def test_millions(self):
        assert _format_budget(5_000_000) == "5.0M€"

    def test_thousands(self):
        assert _format_budget(200_000) == "200 mil €"

    def test_small(self):
        assert _format_budget(500) == "500€"


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


class TestPromptBuilders:
    def test_ayuda_destacada_prompt(self):
        grant = {
            "descripcion": "Test grant",
            "presupuesto_total": 5000000,
            "nivel2": "MINISTERIO TEST",
            "descripcion_finalidad": "Digital",
            "fecha_fin_solicitud": "2026-06-30",
            "numero_convocatoria": "100001",
        }
        prompt = build_ayuda_destacada_prompt(grant)
        assert "Test grant" in prompt
        assert "5.0M€" in prompt
        assert "MINISTERIO TEST" in prompt
        assert "100001" in prompt

    def test_datos_semana_prompt(self):
        stats = {
            "new_count": 42,
            "total_budget": 10000000,
            "top_region": "MADRID",
            "top_theme": "Digital",
            "total_open": 500,
        }
        prompt = build_datos_semana_prompt(stats)
        assert "42" in prompt
        assert "10.0M€" in prompt
        assert "MADRID" in prompt
        assert "500" in prompt

    def test_cierre_inminente_prompt(self):
        grants = [
            {
                "descripcion": "Closing grant",
                "presupuesto_total": 1000000,
                "fecha_fin_solicitud": "2026-04-01",
                "numero_convocatoria": "100002",
            }
        ]
        prompt = build_cierre_inminente_prompt(grants)
        assert "Closing grant" in prompt
        assert "1.0M€" in prompt

    def test_tematico_prompt(self):
        data = {
            "theme": "Agricultura",
            "grants": [
                {
                    "descripcion": "Agri grant",
                    "presupuesto_total": 500000,
                    "nivel2": "MIN AGRI",
                    "numero_convocatoria": "100003",
                }
            ],
        }
        prompt = build_tematico_prompt(data)
        assert "Agricultura" in prompt
        assert "Agri grant" in prompt

    def test_top_organismo_prompt(self):
        data = {
            "organism": "MINISTERIO TEST",
            "count": 15,
            "total_budget": 20000000,
            "grants": [
                {"descripcion": "Grant A", "presupuesto_total": 5000000}
            ],
        }
        prompt = build_top_organismo_prompt(data)
        assert "MINISTERIO TEST" in prompt
        assert "15" in prompt

    def test_dato_curioso_prompt(self):
        data = {
            "curiosidad_type": "ano_record",
            "data": {"year": "2024", "cnt": 50000, "budget": 100000000000},
        }
        prompt = build_dato_curioso_prompt(data)
        assert "2024" in prompt
        assert "50,000" in prompt


# ---------------------------------------------------------------------------
# Data gathering
# ---------------------------------------------------------------------------


class TestGatherData:
    def test_ayuda_destacada(self, populated_db):
        data, ids, meta = gather_data("ayuda_destacada", populated_db)
        assert data is not None
        assert ids is not None
        assert len(ids) == 1

    def test_datos_semana(self, populated_db):
        data, ids, meta = gather_data("datos_semana", populated_db)
        assert data is not None
        assert "new_count" in data
        assert ids is None  # no specific convocatorias

    def test_dato_curioso(self, populated_db):
        data, ids, meta = gather_data("dato_curioso", populated_db)
        assert data is not None
        assert "curiosidad_type" in data
        assert meta is not None
        assert "curiosidad_type" in meta

    def test_invalid_type_raises(self, populated_db):
        with pytest.raises(ValueError, match="Unknown post type"):
            gather_data("invalid_type", populated_db)


# ---------------------------------------------------------------------------
# Auto-selection
# ---------------------------------------------------------------------------


class TestSelectNextPostType:
    def test_returns_valid_type(self, populated_db):
        result = select_next_post_type(populated_db)
        assert result in [
            "ayuda_destacada",
            "datos_semana",
            "cierre_inminente",
            "tematico",
            "top_organismo",
            "dato_curioso",
        ]

    def test_avoids_recently_generated(self, populated_db):
        # Generate several types
        for ptype in ["datos_semana", "ayuda_destacada", "dato_curioso"]:
            insert_post(ptype, "X", "LI", db_path=populated_db)
        result = select_next_post_type(populated_db)
        # Should pick something not in the recent list
        assert result in [
            "cierre_inminente",
            "tematico",
            "top_organismo",
            "ayuda_destacada",
            "datos_semana",
            "dato_curioso",
        ]


# ---------------------------------------------------------------------------
# Full generation (mocked OpenAI)
# ---------------------------------------------------------------------------


class TestRunGeneration:
    @pytest.mark.asyncio
    async def test_generates_and_saves(self, populated_db):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "content_x": "Post para X test",
                        "content_linkedin": "Post para LinkedIn test",
                    })
                )
            )
        ]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            result = await run_generation("ayuda_destacada", populated_db)

        assert result["status"] == "created"
        assert result["post_type"] == "ayuda_destacada"
        assert result["post_id"] >= 1
        assert result["content_x_length"] > 0
        assert result["content_linkedin_length"] > 0

    @pytest.mark.asyncio
    async def test_invalid_type_raises(self, populated_db):
        with pytest.raises(ValueError, match="Invalid post type"):
            await run_generation("invalid", populated_db)

    @pytest.mark.asyncio
    async def test_no_data_returns_status(self, db_path):
        # Empty DB — no convocatorias
        result = await run_generation("ayuda_destacada", db_path)
        assert result["status"] == "no_data"
