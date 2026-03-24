"""Tests for the convocatorias SQLite service."""

import json
import struct

import pytest

from backend.services.convocatorias_db import (
    _build_fts_query,
    _row_to_search_result,
    analytics_by_year,
    analytics_monthly_trend,
    analytics_status,
    analytics_summary,
    analytics_top_organs,
    get_convocatoria_detail_local,
    get_embedding_text,
    get_latest_convocatorias_local,
    get_sync_status,
    get_unfetched_detail_ids,
    get_unembedded_ids,
    init_convocatorias_db,
    rebuild_fts,
    search_convocatorias_local,
    search_fts,
    store_embeddings,
    update_convocatoria_detail,
    upsert_convocatorias_list,
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary DB path and initialize schema."""
    path = str(tmp_path / "test_conv.db")
    init_convocatorias_db(path)
    return path


@pytest.fixture
def sample_records():
    """Sample BDNS-format list records."""
    return [
        {
            "numeroConvocatoria": "100001",
            "descripcion": "Ayudas para digitalización de pymes",
            "descripcionLeng": None,
            "fechaRecepcion": "15/03/2024",
            "organo": {"nivel1": "ESTADO", "nivel2": "MINISTERIO DE INDUSTRIA", "nivel3": "SECRETARIA GENERAL"},
        },
        {
            "numeroConvocatoria": "100002",
            "descripcion": "Becas de investigación universitaria",
            "descripcionLeng": "Beques de recerca universitària",
            "fechaRecepcion": "2024-02-10",
            "organo": {"nivel1": "ESTADO", "nivel2": "MINISTERIO DE CIENCIA", "nivel3": None},
        },
        {
            "numeroConvocatoria": "100003",
            "descripcion": "Subvenciones agricultura sostenible Navarra",
            "descripcionLeng": None,
            "fechaRecepcion": "01/01/2023",
            "organo": {"nivel1": "NAVARRA", "nivel2": "GOBIERNO DE NAVARRA", "nivel3": "DEPARTAMENTO AGRICULTURA"},
        },
    ]


@pytest.fixture
def populated_db(db_path, sample_records):
    """DB with sample convocatorias inserted."""
    upsert_convocatorias_list(sample_records, db_path)
    return db_path


@pytest.fixture
def detailed_db(populated_db):
    """DB with convocatorias that have detail data."""
    update_convocatoria_detail("100001", {
        "presupuestoTotal": 5000000.0,
        "descripcionFinalidad": "Transformación digital",
        "finalidad": {"id": 10},
        "abierto": True,
        "fechaInicioSolicitud": "01/04/2024",
        "fechaFinSolicitud": "30/06/2024",
        "regiones": [{"id": 1, "descripcion": "COMUNIDAD DE MADRID"}],
        "instrumentos": [{"id": 1, "descripcion": "Subvención"}],
        "tiposBeneficiarios": [{"id": 1, "descripcion": "PYME"}],
        "sectores": [{"id": 1, "descripcion": "Tecnología"}],
        "objetivos": [],
        "documentos": [{"id": "doc1", "descripcion": "Bases", "nombreFic": "bases.pdf"}],
        "anuncios": [],
        "sedeElectronica": "https://sede.example.com",
        "urlBasesReguladoras": "https://boe.example.com/bases",
        "descripcionBasesReguladoras": "BOE num 123",
        "tipoConvocatoria": "Competitiva",
        "textInicio": None,
        "textFin": None,
    }, populated_db)

    update_convocatoria_detail("100002", {
        "presupuestoTotal": 2000000.0,
        "descripcionFinalidad": "Investigación científica",
        "finalidad": {"id": 20},
        "abierto": False,
        "fechaInicioSolicitud": None,
        "fechaFinSolicitud": "31/12/2023",
        "regiones": [{"id": 2, "descripcion": "CATALUÑA"}],
        "instrumentos": [],
        "tiposBeneficiarios": [{"id": 2, "descripcion": "Persona física"}],
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
    }, populated_db)

    rebuild_fts(populated_db)
    return populated_db


class TestInitDb:
    """Tests for init_convocatorias_db()."""

    def test_creates_tables(self, db_path):
        import sqlite3
        conn = sqlite3.connect(db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]
        conn.close()

        assert "convocatorias" in table_names
        assert "convocatorias_fts" in table_names
        assert "conv_sync_metadata" in table_names

    def test_idempotent(self, db_path):
        init_convocatorias_db(db_path)
        init_convocatorias_db(db_path)


class TestUpsertList:
    """Tests for upsert_convocatorias_list()."""

    def test_inserts_records(self, db_path, sample_records):
        count = upsert_convocatorias_list(sample_records, db_path)
        assert count == 3

    def test_ignores_duplicates(self, populated_db, sample_records):
        count = upsert_convocatorias_list(sample_records, populated_db)
        assert count == 0

    def test_converts_dates(self, db_path):
        records = [
            {
                "numeroConvocatoria": "200001",
                "descripcion": "Test",
                "fechaRecepcion": "15/06/2024",
                "organo": {},
            }
        ]
        upsert_convocatorias_list(records, db_path)
        status = get_sync_status(db_path)
        assert status["total"] == 1


class TestUpdateDetail:
    """Tests for update_convocatoria_detail()."""

    def test_updates_detail(self, populated_db):
        result = update_convocatoria_detail("100001", {
            "presupuestoTotal": 1000000.0,
            "abierto": True,
        }, populated_db)
        assert result is True

        detail = get_convocatoria_detail_local("100001", populated_db)
        assert detail is not None
        assert detail["presupuestoTotal"] == 1000000.0
        assert detail["abierto"] is True

    def test_nonexistent_record(self, populated_db):
        result = update_convocatoria_detail("999999", {"presupuestoTotal": 100}, populated_db)
        assert result is False


class TestGetUnfetchedDetailIds:
    """Tests for get_unfetched_detail_ids()."""

    def test_returns_all_without_detail(self, populated_db):
        ids = get_unfetched_detail_ids(db_path=populated_db)
        assert len(ids) == 3

    def test_excludes_fetched(self, detailed_db):
        ids = get_unfetched_detail_ids(db_path=detailed_db)
        assert "100001" not in ids
        assert "100002" not in ids
        assert "100003" in ids

    def test_respects_limit(self, populated_db):
        ids = get_unfetched_detail_ids(limit=1, db_path=populated_db)
        assert len(ids) == 1


class TestGetUnembeddedIds:
    """Tests for get_unembedded_ids()."""

    def test_returns_detailed_without_embedding(self, detailed_db):
        ids = get_unembedded_ids(db_path=detailed_db)
        nums = [num for _, num in ids]
        assert "100001" in nums
        assert "100002" in nums
        assert "100003" not in nums  # no detail = not eligible


class TestStoreEmbeddings:
    """Tests for store_embeddings()."""

    def test_stores_blob(self, detailed_db):
        ids = get_unembedded_ids(db_path=detailed_db)
        assert len(ids) > 0

        fake_embedding = [0.1] * 1536
        blob = struct.pack(f"<{len(fake_embedding)}f", *fake_embedding)
        records = [(ids[0][0], blob)]

        count = store_embeddings(records, detailed_db)
        assert count == 1

        # Verify it's no longer unembedded
        remaining = get_unembedded_ids(db_path=detailed_db)
        remaining_nums = [num for _, num in remaining]
        assert ids[0][1] not in remaining_nums


class TestSearchFts:
    """Tests for search_fts()."""

    def test_finds_by_keyword(self, detailed_db):
        results = search_fts("digitalización", db_path=detailed_db)
        assert len(results) >= 1
        assert any(r["numero_convocatoria"] == "100001" for r in results)

    def test_finds_by_finalidad(self, detailed_db):
        results = search_fts("investigación", db_path=detailed_db)
        assert len(results) >= 1

    def test_empty_query(self, detailed_db):
        results = search_fts("", db_path=detailed_db)
        assert results == []

    def test_no_results(self, detailed_db):
        results = search_fts("xyznonexistent", db_path=detailed_db)
        assert results == []


class TestGetDetailLocal:
    """Tests for get_convocatoria_detail_local()."""

    def test_returns_bdns_format(self, detailed_db):
        detail = get_convocatoria_detail_local("100001", detailed_db)
        assert detail is not None
        assert detail["codigoBDNS"] == "100001"
        assert detail["descripcion"] == "Ayudas para digitalización de pymes"
        assert detail["presupuestoTotal"] == 5000000.0
        assert detail["abierto"] is True
        assert detail["sedeElectronica"] == "https://sede.example.com"
        assert len(detail["regiones"]) == 1
        assert detail["regiones"][0]["descripcion"] == "COMUNIDAD DE MADRID"
        assert len(detail["documentos"]) == 1
        assert detail["organo"]["nivel1"] == "ESTADO"

    def test_returns_none_without_detail(self, populated_db):
        detail = get_convocatoria_detail_local("100001", populated_db)
        assert detail is None

    def test_returns_none_for_nonexistent(self, detailed_db):
        detail = get_convocatoria_detail_local("999999", detailed_db)
        assert detail is None


class TestGetSyncStatus:
    """Tests for get_sync_status()."""

    def test_empty_db(self, db_path):
        status = get_sync_status(db_path)
        assert status["total"] == 0
        assert status["with_detail"] == 0
        assert status["with_embedding"] == 0
        assert status["last_sync"] is None

    def test_with_data(self, detailed_db):
        status = get_sync_status(detailed_db)
        assert status["total"] == 3
        assert status["with_detail"] == 2
        assert status["with_embedding"] == 0


class TestGetEmbeddingText:
    """Tests for get_embedding_text()."""

    def test_builds_text_from_dict(self):
        row = {
            "descripcion": "Ayudas digitalización",
            "descripcion_leng": None,
            "descripcion_finalidad": "Transformación digital",
            "nivel1": "ESTADO",
            "nivel2": "MINISTERIO",
            "nivel3": "SECRETARIA",
            "tipos_beneficiarios_json": json.dumps([{"descripcion": "PYME"}]),
            "regiones_json": json.dumps([{"descripcion": "Madrid"}]),
            "instrumentos_json": None,
            "sectores_json": None,
            "objetivos_json": None,
        }
        text = get_embedding_text(row)
        assert "Ayudas digitalización" in text
        assert "Transformación digital" in text
        assert "SECRETARIA - MINISTERIO - ESTADO" in text
        assert "PYME" in text
        assert "Madrid" in text


class TestBuildFtsQuery:
    """Tests for _build_fts_query()."""

    def test_single_word(self):
        assert _build_fts_query("diabetes") == '"diabetes"'

    def test_multiple_words(self):
        assert _build_fts_query("ayudas diabetes") == '"ayudas" "diabetes"'

    def test_empty(self):
        assert _build_fts_query("") == ""


class TestAnalytics:
    """Tests for analytics query functions."""

    def test_by_year(self, detailed_db):
        data = analytics_by_year(detailed_db)
        assert len(data) >= 1
        years = [d["label"] for d in data]
        assert "2024" in years

    def test_monthly_trend(self, detailed_db):
        data = analytics_monthly_trend(2024, detailed_db)
        assert isinstance(data, list)
        for item in data:
            assert "label" in item
            assert "count" in item

    def test_top_organs(self, detailed_db):
        data = analytics_top_organs(db_path=detailed_db)
        assert isinstance(data, list)
        if data:
            assert "label" in data[0]
            assert "count" in data[0]

    def test_status(self, detailed_db):
        data = analytics_status(detailed_db)
        assert "open" in data
        assert "closed" in data
        assert data["open"] + data["closed"] == data["total"]

    def test_summary(self, detailed_db):
        data = analytics_summary(detailed_db)
        assert data["total"] == 3
        assert data["total_budget"] > 0


class TestRowToSearchResultRegion:
    """Tests for _row_to_search_result() region label extraction."""

    def _make_row(self, regiones_json=None):
        """Create a minimal dict mimicking a SQLite Row."""
        return {
            "numero_convocatoria": "100001",
            "descripcion": "Test grant",
            "descripcion_leng": None,
            "fecha_recepcion": "2024-03-15",
            "nivel1": "ESTADO",
            "nivel2": "MINISTERIO",
            "nivel3": None,
            "presupuesto_total": 1000,
            "abierto": True,
            "fecha_inicio_solicitud": "2024-04-01",
            "fecha_fin_solicitud": "2026-12-31",
            "text_inicio": None,
            "text_fin": None,
            "regiones_json": regiones_json,
        }

    def test_single_region(self):
        row = self._make_row(json.dumps([{"id": 1, "descripcion": "COMUNIDAD DE MADRID"}]))
        result = _row_to_search_result(row)
        assert result["_regionLabel"] == "COMUNIDAD DE MADRID"

    def test_multiple_regions_returns_first(self):
        row = self._make_row(json.dumps([
            {"id": 1, "descripcion": "CATALUÑA"},
            {"id": 2, "descripcion": "ARAGON"},
        ]))
        result = _row_to_search_result(row)
        assert result["_regionLabel"] == "CATALUÑA"

    def test_null_regiones(self):
        row = self._make_row(None)
        result = _row_to_search_result(row)
        assert result["_regionLabel"] is None

    def test_empty_array(self):
        row = self._make_row(json.dumps([]))
        result = _row_to_search_result(row)
        assert result["_regionLabel"] is None

    def test_no_regiones_json_key(self):
        """Row without regiones_json column (e.g. older query)."""
        row = {
            "numero_convocatoria": "100001",
            "descripcion": "Test",
            "fecha_recepcion": "2024-03-15",
            "nivel1": "ESTADO",
            "nivel2": "MINISTERIO",
            "nivel3": None,
            "presupuesto_total": 1000,
            "abierto": True,
            "fecha_inicio_solicitud": "2024-04-01",
            "fecha_fin_solicitud": "2026-12-31",
        }
        result = _row_to_search_result(row)
        assert result["_regionLabel"] is None


class TestRegionInSearchResults:
    """Tests that region label appears in search and latest results."""

    def test_latest_includes_region_label(self, detailed_db):
        results = get_latest_convocatorias_local(0, 20, detailed_db)
        # 100001 has region COMUNIDAD DE MADRID
        grant_100001 = next(
            (g for g in results["content"] if g["numeroConvocatoria"] == "100001"),
            None,
        )
        assert grant_100001 is not None
        assert grant_100001["_regionLabel"] == "COMUNIDAD DE MADRID"

    def test_latest_non_closed_before_closed(self, detailed_db):
        """Latest listing should show non-closed grants before closed ones."""
        results = get_latest_convocatorias_local(0, 20, detailed_db)
        statuses = [g["_status"] for g in results["content"]]
        # 100002 has fechaFinSolicitud=2023-12-31 (closed), 100001 has 2024-06-30
        # Non-closed should appear before closed
        closed_indices = [i for i, s in enumerate(statuses) if s == "closed"]
        non_closed_indices = [i for i, s in enumerate(statuses) if s != "closed"]
        if closed_indices and non_closed_indices:
            assert max(non_closed_indices) < min(closed_indices)

    def test_search_includes_region_label(self, detailed_db):
        results = search_convocatorias_local(
            q="digitalización", db_path=detailed_db,
        )
        assert len(results["content"]) >= 1
        grant = results["content"][0]
        assert "_regionLabel" in grant


class TestSearchSortNonClosedFirst:
    """Tests that text search sorts non-closed grants before closed ones."""

    @pytest.fixture
    def mixed_status_db(self, db_path):
        """DB with grants that have mixed open/closed status."""
        records = [
            {
                "numeroConvocatoria": "200001",
                "descripcion": "Ayudas para innovación tecnológica abierta",
                "fechaRecepcion": "2024-06-01",
                "organo": {"nivel1": "ESTADO", "nivel2": "MIN CIENCIA"},
            },
            {
                "numeroConvocatoria": "200002",
                "descripcion": "Ayudas para innovación tecnológica cerrada antigua",
                "fechaRecepcion": "2024-07-01",
                "organo": {"nivel1": "ESTADO", "nivel2": "MIN INDUSTRIA"},
            },
            {
                "numeroConvocatoria": "200003",
                "descripcion": "Ayudas para innovación tecnológica abierta reciente",
                "fechaRecepcion": "2024-08-01",
                "organo": {"nivel1": "ESTADO", "nivel2": "MIN ECONOMIA"},
            },
        ]
        upsert_convocatorias_list(records, db_path)

        # 200001: open (far future end date)
        update_convocatoria_detail("200001", {
            "presupuestoTotal": 100,
            "abierto": True,
            "fechaFinSolicitud": "31/12/2030",
        }, db_path)

        # 200002: closed (past end date)
        update_convocatoria_detail("200002", {
            "presupuestoTotal": 200,
            "abierto": False,
            "fechaFinSolicitud": "01/01/2020",
        }, db_path)

        # 200003: open (far future end date)
        update_convocatoria_detail("200003", {
            "presupuestoTotal": 300,
            "abierto": True,
            "fechaFinSolicitud": "31/12/2030",
        }, db_path)

        rebuild_fts(db_path)
        return db_path

    def test_non_closed_before_closed_with_text_search(self, mixed_status_db):
        results = search_convocatorias_local(
            q="innovación", db_path=mixed_status_db,
        )
        codes = [g["numeroConvocatoria"] for g in results["content"]]
        assert len(codes) == 3

        # Non-closed grants (200003, 200001) should come before closed (200002)
        # Within non-closed: sorted by date desc → 200003 (Aug) before 200001 (Jun)
        idx_200001 = codes.index("200001")
        idx_200002 = codes.index("200002")
        idx_200003 = codes.index("200003")
        assert idx_200003 < idx_200002, "Open grant 200003 should appear before closed 200002"
        assert idx_200001 < idx_200002, "Open grant 200001 should appear before closed 200002"
        assert idx_200003 < idx_200001, "More recent open grant 200003 should appear before 200001"

    def test_no_text_search_keeps_chronological_order(self, mixed_status_db):
        """Without text search, normal chronological order is preserved."""
        results = search_convocatorias_local(db_path=mixed_status_db)
        codes = [g["numeroConvocatoria"] for g in results["content"]]
        # Pure date desc: 200003 (Aug), 200002 (Jul), 200001 (Jun)
        assert codes == ["200003", "200002", "200001"]
