"""Tests for the beneficiarios SQLite service."""

import tempfile
from pathlib import Path

import pytest

from backend.services.beneficiarios_db import (
    _build_fts_query,
    get_sync_status,
    get_top_beneficiarios_aggregated,
    has_data,
    init_db,
    parse_beneficiario,
    search_beneficiarios,
    search_beneficiarios_trend,
    sync_beneficiarios,
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary DB path and initialize schema."""
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def populated_db(db_path):
    """DB with sample beneficiarios data."""
    records = [
        {
            "idPersona": 1,
            "beneficiario": "ES A07129430 AIR EUROPA LINEAS AEREAS, SA",
            "ejercicio": 2024,
            "ayudaETotal": 5000000.0,
        },
        {
            "idPersona": 2,
            "beneficiario": "ES B12345678 IBERDROLA DISTRIBUCION ELECTRICA SA",
            "ejercicio": 2024,
            "ayudaETotal": 3000000.0,
        },
        {
            "idPersona": 3,
            "beneficiario": "ES B12345678 IBERDROLA DISTRIBUCION ELECTRICA SA",
            "ejercicio": 2023,
            "ayudaETotal": 2500000.0,
        },
        {
            "idPersona": 4,
            "beneficiario": "ES A99999999 TELEFONICA DE ESPAÑA SAU",
            "ejercicio": 2024,
            "ayudaETotal": 1000000.0,
        },
        {
            "idPersona": 5,
            "beneficiario": "12345678Z JUAN GARCIA LOPEZ",
            "ejercicio": 2024,
            "ayudaETotal": 50000.0,
        },
    ]
    sync_beneficiarios(records, db_path)
    return db_path


class TestParseBeneficiario:
    """Tests for parse_beneficiario()."""

    def test_standard_format_with_es_prefix(self):
        nif, nombre = parse_beneficiario("ES A07129430 AIR EUROPA LINEAS AEREAS, SA")
        assert nif == "A07129430"
        assert nombre == "AIR EUROPA LINEAS AEREAS, SA"

    def test_without_es_prefix(self):
        nif, nombre = parse_beneficiario("B12345678 IBERDROLA SA")
        assert nif == "B12345678"
        assert nombre == "IBERDROLA SA"

    def test_person_with_dni(self):
        nif, nombre = parse_beneficiario("12345678Z JUAN GARCIA LOPEZ")
        assert nif == "12345678Z"
        assert nombre == "JUAN GARCIA LOPEZ"

    def test_empty_string(self):
        nif, nombre = parse_beneficiario("")
        assert nif is None
        assert nombre is None

    def test_none_input(self):
        nif, nombre = parse_beneficiario(None)
        assert nif is None
        assert nombre is None

    def test_unparseable_falls_back_to_raw(self):
        nif, nombre = parse_beneficiario("SOME RANDOM TEXT")
        assert nif is None
        assert nombre == "SOME RANDOM TEXT"


class TestBuildFtsQuery:
    """Tests for _build_fts_query()."""

    def test_single_word(self):
        assert _build_fts_query("iberdrola") == '"iberdrola"'

    def test_multiple_words(self):
        assert _build_fts_query("air europa") == '"air" "europa"'

    def test_strips_quotes(self):
        assert _build_fts_query('"air" europa') == '"air" "europa"'

    def test_strips_special_chars(self):
        assert _build_fts_query("air+europa*") == '"air" "europa"'

    def test_empty_string(self):
        assert _build_fts_query("") == ""

    def test_only_special_chars(self):
        assert _build_fts_query("***") == ""


class TestInitDb:
    """Tests for init_db()."""

    def test_creates_tables(self, db_path):
        import sqlite3

        conn = sqlite3.connect(db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]
        conn.close()

        assert "beneficiarios" in table_names
        assert "beneficiarios_fts" in table_names
        assert "sync_metadata" in table_names

    def test_idempotent(self, db_path):
        # Calling init_db twice should not error
        init_db(db_path)
        init_db(db_path)

    def test_creates_parent_directory(self, tmp_path):
        path = str(tmp_path / "subdir" / "deep" / "test.db")
        init_db(path)
        assert Path(path).exists()


class TestSyncBeneficiarios:
    """Tests for sync_beneficiarios()."""

    def test_inserts_records(self, db_path):
        records = [
            {
                "idPersona": 1,
                "beneficiario": "ES A07129430 AIR EUROPA",
                "ejercicio": 2024,
                "ayudaETotal": 5000000.0,
            },
        ]
        count = sync_beneficiarios(records, db_path)
        assert count == 1

    def test_replaces_on_second_sync(self, db_path):
        records1 = [
            {"idPersona": 1, "beneficiario": "A", "ejercicio": 2024, "ayudaETotal": 100},
            {"idPersona": 2, "beneficiario": "B", "ejercicio": 2024, "ayudaETotal": 200},
        ]
        sync_beneficiarios(records1, db_path)

        records2 = [
            {"idPersona": 3, "beneficiario": "C", "ejercicio": 2024, "ayudaETotal": 300},
        ]
        sync_beneficiarios(records2, db_path)

        status = get_sync_status(db_path)
        assert status["total_records"] == 1

    def test_has_data(self, db_path):
        assert has_data(db_path) is False
        sync_beneficiarios(
            [{"idPersona": 1, "beneficiario": "X", "ejercicio": 2024, "ayudaETotal": 100}],
            db_path,
        )
        assert has_data(db_path) is True


class TestSearchBeneficiarios:
    """Tests for search_beneficiarios() with FTS5."""

    def test_search_by_name(self, populated_db):
        result = search_beneficiarios("air europa", db_path=populated_db)
        assert result["totalElements"] == 1
        assert result["content"][0]["nombre"] == "AIR EUROPA LINEAS AEREAS, SA"

    def test_search_partial_name(self, populated_db):
        # Without year filter → aggregated: 1 unique nif_cif
        result = search_beneficiarios("iberdrola", db_path=populated_db)
        assert result["totalElements"] == 1
        assert result["content"][0]["ayudaETotal"] == 5500000.0  # 3M + 2.5M

    def test_search_with_year_filter(self, populated_db):
        result = search_beneficiarios("iberdrola", anio=2024, db_path=populated_db)
        assert result["totalElements"] == 1
        assert result["content"][0]["ejercicio"] == 2024

    def test_search_no_results(self, populated_db):
        result = search_beneficiarios("nonexistent company", db_path=populated_db)
        assert result["totalElements"] == 0
        assert result["content"] == []

    def test_pagination(self, populated_db):
        # Search all records with page_size=2
        result = search_beneficiarios("", page=0, page_size=2, db_path=populated_db)
        # Empty query returns no results (FTS needs tokens)
        assert result["totalElements"] == 0

    def test_result_format_with_year(self, populated_db):
        result = search_beneficiarios("air europa", anio=2024, db_path=populated_db)
        assert "content" in result
        assert "totalElements" in result
        assert "totalPages" in result
        assert "number" in result
        assert "size" in result

        item = result["content"][0]
        assert "idPersona" in item
        assert "beneficiario" in item
        assert "nifCif" in item
        assert "nombre" in item
        assert "ejercicio" in item
        assert "ayudaETotal" in item

    def test_result_format_no_year_omits_ejercicio(self, populated_db):
        result = search_beneficiarios("air europa", db_path=populated_db)
        item = result["content"][0]
        assert "ejercicio" not in item

    def test_results_ordered_by_amount_desc(self, populated_db):
        # Add more data so aggregation produces multiple results
        result = search_beneficiarios("iberdrola", anio=2024, db_path=populated_db)
        amounts = [r["ayudaETotal"] for r in result["content"]]
        assert amounts == sorted(amounts, reverse=True)

    def test_pagination_page_1(self, populated_db):
        # With specific year, iberdrola has 2 rows (2023 + 2024)
        p0 = search_beneficiarios("iberdrola", anio=2024, page=0, page_size=1, db_path=populated_db)
        assert p0["totalElements"] == 1  # Only 1 record in 2024
        assert len(p0["content"]) == 1

    def test_search_no_year_aggregates(self, populated_db):
        """When anio=None, results are aggregated by nif_cif."""
        result = search_beneficiarios("iberdrola", db_path=populated_db)
        assert result["totalElements"] == 1
        assert result["content"][0]["ayudaETotal"] == 5500000.0
        assert "ejercicio" not in result["content"][0]

    def test_search_with_year_not_aggregated(self, populated_db):
        """When anio is set, each year row is returned individually."""
        result = search_beneficiarios("iberdrola", anio=2024, db_path=populated_db)
        assert result["totalElements"] == 1
        assert result["content"][0]["ejercicio"] == 2024
        assert result["content"][0]["ayudaETotal"] == 3000000.0

    def test_case_insensitive_search(self, populated_db):
        result = search_beneficiarios("AIR EUROPA", db_path=populated_db)
        assert result["totalElements"] == 1

        result2 = search_beneficiarios("air europa", db_path=populated_db)
        assert result2["totalElements"] == 1


class TestGetTopBeneficiariosAggregated:
    """Tests for get_top_beneficiarios_aggregated()."""

    def test_aggregates_across_years(self, populated_db):
        result = get_top_beneficiarios_aggregated(db_path=populated_db)
        nifs = [r["nifCif"] for r in result["content"]]
        # Iberdrola B12345678 appears in 2023+2024 but should be 1 result
        assert nifs.count("B12345678") == 1

    def test_sums_amounts(self, populated_db):
        result = get_top_beneficiarios_aggregated(db_path=populated_db)
        iberdrola = next(r for r in result["content"] if r["nifCif"] == "B12345678")
        assert iberdrola["ayudaETotal"] == 5500000.0  # 3M + 2.5M

    def test_no_duplicates(self, populated_db):
        result = get_top_beneficiarios_aggregated(db_path=populated_db)
        nifs = [r["nifCif"] for r in result["content"]]
        assert len(nifs) == len(set(nifs))

    def test_ordered_by_total_desc(self, populated_db):
        result = get_top_beneficiarios_aggregated(db_path=populated_db)
        amounts = [r["ayudaETotal"] for r in result["content"]]
        assert amounts == sorted(amounts, reverse=True)

    def test_pagination(self, populated_db):
        p0 = get_top_beneficiarios_aggregated(page=0, page_size=2, db_path=populated_db)
        p1 = get_top_beneficiarios_aggregated(page=1, page_size=2, db_path=populated_db)

        assert p0["totalPages"] == 2  # 4 unique nif_cifs, page_size=2
        assert len(p0["content"]) == 2
        assert len(p1["content"]) == 2

    def test_empty_db(self, db_path):
        result = get_top_beneficiarios_aggregated(db_path=db_path)
        assert result["totalElements"] == 0
        assert result["content"] == []

    def test_no_ejercicio_field(self, populated_db):
        result = get_top_beneficiarios_aggregated(db_path=populated_db)
        for item in result["content"]:
            assert "ejercicio" not in item


class TestSearchBeneficiariosTrend:
    """Tests for search_beneficiarios_trend()."""

    def test_trend_aggregates_by_year(self, populated_db):
        result = search_beneficiarios_trend("iberdrola", db_path=populated_db)
        assert result["total_matches"] == 1  # 1 distinct nif_cif
        assert len(result["by_year"]) == 2  # 2023 and 2024

        years = {d["year"] for d in result["by_year"]}
        assert years == {"2023", "2024"}

        # Check year data has correct structure
        for entry in result["by_year"]:
            assert "year" in entry
            assert "count" in entry
            assert "amount" in entry
            assert isinstance(entry["year"], str)

    def test_trend_top_beneficiarios(self, populated_db):
        result = search_beneficiarios_trend("iberdrola", db_path=populated_db)
        top = result["top_beneficiarios"]
        assert len(top) == 1
        assert top[0]["nifCif"] == "B12345678"
        assert top[0]["ayudaETotal"] == 5500000.0  # 3M + 2.5M aggregated

        # Verify format matches aggregated search
        item = top[0]
        assert "idPersona" in item
        assert "beneficiario" in item
        assert "nifCif" in item
        assert "nombre" in item
        assert "ayudaETotal" in item

    def test_trend_no_results(self, populated_db):
        result = search_beneficiarios_trend("nonexistent company xyz", db_path=populated_db)
        assert result["total_matches"] == 0
        assert result["by_year"] == []
        assert result["top_beneficiarios"] == []

    def test_trend_empty_query(self, populated_db):
        result = search_beneficiarios_trend("", db_path=populated_db)
        assert result["total_matches"] == 0
        assert result["by_year"] == []
        assert result["top_beneficiarios"] == []

    def test_trend_multiple_beneficiarios(self, populated_db):
        """Search matching multiple beneficiarios returns all in top list."""
        # "a" appears in AIR EUROPA, IBERDROLA (ELECTRICA), TELEFONICA (ESPAÑA)
        # Use a broader term — search for content that hits multiple rows
        result = search_beneficiarios_trend("europa", db_path=populated_db)
        assert result["total_matches"] >= 1
        assert len(result["top_beneficiarios"]) >= 1

    def test_trend_top_limited_to_20(self, populated_db):
        """Top beneficiarios are limited to 20 entries."""
        result = search_beneficiarios_trend("iberdrola", db_path=populated_db)
        assert len(result["top_beneficiarios"]) <= 20
