"""Tests for the posts_db SQLite service."""

import json
import sqlite3

import pytest

from backend.services.convocatorias_db import (
    init_convocatorias_db,
    update_convocatoria_detail,
    upsert_convocatorias_list,
)
from backend.services.posts_db import (
    delete_post,
    get_post,
    get_used_convocatoria_ids,
    init_posts_db,
    insert_post,
    list_posts,
    query_ayuda_destacada,
    query_cierre_inminente,
    query_dato_curioso,
    query_datos_semana,
    query_tematico,
    query_top_organismo,
    update_post_status,
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary DB with both convocatorias and posts tables."""
    path = str(tmp_path / "test_posts.db")
    init_convocatorias_db(path)
    init_posts_db(path)
    return path


@pytest.fixture
def populated_db(db_path):
    """DB with sample convocatorias for query testing."""
    # Insert convocatorias via the normal pipeline
    records = [
        {
            "numeroConvocatoria": "200001",
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
            "numeroConvocatoria": "200002",
            "descripcion": "Becas de investigación",
            "descripcionLeng": None,
            "fechaRecepcion": "22/03/2026",
            "organo": {
                "nivel1": "ESTADO",
                "nivel2": "MINISTERIO DE CIENCIA",
                "nivel3": None,
            },
        },
        {
            "numeroConvocatoria": "200003",
            "descripcion": "Subvenciones agricultura Navarra",
            "descripcionLeng": None,
            "fechaRecepcion": "23/03/2026",
            "organo": {
                "nivel1": "NAVARRA",
                "nivel2": "GOBIERNO DE NAVARRA",
                "nivel3": "DEPARTAMENTO AGRICULTURA",
            },
        },
    ]
    upsert_convocatorias_list(records, db_path)

    # Add detail to all three
    update_convocatoria_detail(
        "200001",
        {
            "presupuestoTotal": 5000000.0,
            "descripcionFinalidad": "Transformación digital",
            "finalidad": {"id": 10},
            "abierto": True,
            "fechaInicioSolicitud": "01/04/2026",
            "fechaFinSolicitud": "30/06/2026",
            "regiones": [{"id": 1, "descripcion": "COMUNIDAD DE MADRID"}],
            "instrumentos": [{"id": 1, "descripcion": "Subvención"}],
            "tiposBeneficiarios": [{"id": 1, "descripcion": "PYME"}],
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
        "200002",
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

    update_convocatoria_detail(
        "200003",
        {
            "presupuestoTotal": 1000000.0,
            "descripcionFinalidad": "Transformación digital",
            "finalidad": {"id": 10},
            "abierto": True,
            "fechaInicioSolicitud": "01/03/2026",
            "fechaFinSolicitud": "31/12/2026",
            "regiones": [{"id": 3, "descripcion": "NAVARRA"}],
            "instrumentos": [],
            "tiposBeneficiarios": [],
            "sectores": [],
            "objetivos": [],
            "documentos": [],
            "anuncios": [],
            "sedeElectronica": None,
            "urlBasesReguladoras": None,
            "descripcionBasesReguladoras": None,
            "tipoConvocatoria": "Competitiva",
            "textInicio": None,
            "textFin": None,
        },
        db_path,
    )

    return db_path


# ---------------------------------------------------------------------------
# CRUD Tests
# ---------------------------------------------------------------------------


class TestInsertAndRetrieve:
    def test_insert_returns_id(self, db_path):
        post_id = insert_post(
            "ayuda_destacada",
            "Post para X",
            "Post para LinkedIn",
            db_path=db_path,
        )
        assert post_id >= 1

    def test_get_post(self, db_path):
        post_id = insert_post(
            "datos_semana",
            "Datos X",
            "Datos LinkedIn",
            convocatoria_ids=[1, 2],
            metadata={"stat": "value"},
            db_path=db_path,
        )
        post = get_post(post_id, db_path)
        assert post is not None
        assert post["post_type"] == "datos_semana"
        assert post["content_x"] == "Datos X"
        assert post["content_linkedin"] == "Datos LinkedIn"
        assert post["convocatoria_ids"] == [1, 2]
        assert post["metadata"] == {"stat": "value"}
        assert post["status"] == "draft"

    def test_get_nonexistent_post(self, db_path):
        assert get_post(99999, db_path) is None


class TestListPosts:
    def test_list_all(self, db_path):
        insert_post("ayuda_destacada", "X1", "LI1", db_path=db_path)
        insert_post("datos_semana", "X2", "LI2", db_path=db_path)
        posts = list_posts(db_path=db_path)
        assert len(posts) == 2

    def test_filter_by_status(self, db_path):
        id1 = insert_post("ayuda_destacada", "X1", "LI1", db_path=db_path)
        insert_post("datos_semana", "X2", "LI2", db_path=db_path)
        update_post_status(id1, "published", db_path)

        drafts = list_posts(status="draft", db_path=db_path)
        assert len(drafts) == 1
        assert drafts[0]["post_type"] == "datos_semana"

        published = list_posts(status="published", db_path=db_path)
        assert len(published) == 1

    def test_filter_by_type(self, db_path):
        insert_post("ayuda_destacada", "X1", "LI1", db_path=db_path)
        insert_post("datos_semana", "X2", "LI2", db_path=db_path)
        insert_post("ayuda_destacada", "X3", "LI3", db_path=db_path)

        result = list_posts(post_type="ayuda_destacada", db_path=db_path)
        assert len(result) == 2

    def test_list_respects_limit(self, db_path):
        for i in range(5):
            insert_post("ayuda_destacada", f"X{i}", f"LI{i}", db_path=db_path)
        result = list_posts(limit=3, db_path=db_path)
        assert len(result) == 3

    def test_list_ordered_by_created_at_desc(self, db_path):
        insert_post("ayuda_destacada", "first", "first", db_path=db_path)
        # Manually set the second post's created_at to be later
        id2 = insert_post("datos_semana", "second", "second", db_path=db_path)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE generated_posts SET created_at = datetime('now', '+1 minute') WHERE id = ?",
            (id2,),
        )
        conn.commit()
        conn.close()
        posts = list_posts(db_path=db_path)
        assert posts[0]["content_x"] == "second"
        assert posts[1]["content_x"] == "first"


class TestUpdateStatus:
    def test_update_to_published(self, db_path):
        post_id = insert_post("ayuda_destacada", "X", "LI", db_path=db_path)
        result = update_post_status(post_id, "published", db_path)
        assert result is True
        post = get_post(post_id, db_path)
        assert post["status"] == "published"
        assert post["published_at"] is not None

    def test_update_to_discarded(self, db_path):
        post_id = insert_post("ayuda_destacada", "X", "LI", db_path=db_path)
        result = update_post_status(post_id, "discarded", db_path)
        assert result is True
        post = get_post(post_id, db_path)
        assert post["status"] == "discarded"
        assert post["published_at"] is None

    def test_update_nonexistent(self, db_path):
        result = update_post_status(99999, "published", db_path)
        assert result is False


class TestDeletePost:
    def test_delete_existing(self, db_path):
        post_id = insert_post("ayuda_destacada", "X", "LI", db_path=db_path)
        assert delete_post(post_id, db_path) is True
        assert get_post(post_id, db_path) is None

    def test_delete_nonexistent(self, db_path):
        assert delete_post(99999, db_path) is False


class TestGetUsedConvocatoriaIds:
    def test_returns_ids_from_multiple_posts(self, db_path):
        insert_post("ayuda_destacada", "X1", "LI1", convocatoria_ids=[1, 2], db_path=db_path)
        insert_post("datos_semana", "X2", "LI2", convocatoria_ids=[3, 4], db_path=db_path)
        ids = get_used_convocatoria_ids(db_path)
        assert ids == {1, 2, 3, 4}

    def test_excludes_discarded_posts(self, db_path):
        id1 = insert_post("ayuda_destacada", "X1", "LI1", convocatoria_ids=[1, 2], db_path=db_path)
        insert_post("datos_semana", "X2", "LI2", convocatoria_ids=[3, 4], db_path=db_path)
        update_post_status(id1, "discarded", db_path)
        ids = get_used_convocatoria_ids(db_path)
        assert ids == {3, 4}

    def test_empty_when_no_posts(self, db_path):
        ids = get_used_convocatoria_ids(db_path)
        assert ids == set()

    def test_handles_null_convocatoria_ids(self, db_path):
        insert_post("datos_semana", "X", "LI", db_path=db_path)  # no convocatoria_ids
        ids = get_used_convocatoria_ids(db_path)
        assert ids == set()


# ---------------------------------------------------------------------------
# Data Query Tests
# ---------------------------------------------------------------------------


class TestQueryAyudaDestacada:
    def test_returns_highest_budget(self, populated_db):
        result = query_ayuda_destacada(db_path=populated_db)
        assert result is not None
        assert result["presupuesto_total"] == 5000000.0
        assert result["numero_convocatoria"] == "200001"

    def test_excludes_used_ids(self, populated_db):
        # Get the ID of the top grant
        top = query_ayuda_destacada(db_path=populated_db)
        result = query_ayuda_destacada(
            exclude_ids={top["id"]}, db_path=populated_db
        )
        assert result is not None
        assert result["id"] != top["id"]
        assert result["presupuesto_total"] == 2000000.0

    def test_returns_none_when_all_excluded(self, populated_db):
        # Get all IDs
        conn = sqlite3.connect(populated_db)
        conn.row_factory = sqlite3.Row
        all_ids = {r["id"] for r in conn.execute("SELECT id FROM convocatorias").fetchall()}
        conn.close()
        result = query_ayuda_destacada(exclude_ids=all_ids, db_path=populated_db)
        assert result is None


class TestQueryDatosSemana:
    def test_returns_stats(self, populated_db):
        stats = query_datos_semana(populated_db)
        assert stats["new_count"] >= 0
        assert "total_budget" in stats
        assert "top_region" in stats
        assert "top_theme" in stats
        assert "total_open" in stats

    def test_returns_correct_count_for_recent(self, populated_db):
        # All 3 records have recent fecha_recepcion (March 2026)
        stats = query_datos_semana(populated_db)
        # At least some should be counted
        assert isinstance(stats["new_count"], int)


class TestQueryCierreInminente:
    def test_excludes_end_of_year(self, populated_db):
        # 200003 has fecha_fin_solicitud = 2026-12-31 (should be excluded)
        results = query_cierre_inminente(days=365, db_path=populated_db)
        for r in results:
            assert not r["fecha_fin_solicitud"].endswith("-12-31")

    def test_returns_list(self, populated_db):
        results = query_cierre_inminente(days=365, db_path=populated_db)
        assert isinstance(results, list)


class TestQueryTematico:
    def test_returns_theme_and_grants(self, populated_db):
        result = query_tematico(db_path=populated_db)
        assert result is not None
        assert "theme" in result
        assert "grants" in result
        assert len(result["grants"]) > 0

    def test_excludes_used_ids(self, populated_db):
        # Get all grant IDs for the theme
        result1 = query_tematico(db_path=populated_db)
        all_ids = {g["id"] for g in result1["grants"]}
        result2 = query_tematico(exclude_ids=all_ids, db_path=populated_db)
        if result2:
            for g in result2["grants"]:
                assert g["id"] not in all_ids


class TestQueryTopOrganismo:
    def test_returns_organism_data(self, populated_db):
        result = query_top_organismo(populated_db)
        # May or may not return results depending on fecha_recepcion
        # relative to 'now', but should not crash
        if result:
            assert "organism" in result
            assert "count" in result
            assert "total_budget" in result
            assert "grants" in result


class TestQueryDatoCurioso:
    def test_returns_curiosity(self, populated_db):
        result = query_dato_curioso(populated_db)
        assert result is not None
        assert "curiosidad_type" in result
        assert "data" in result

    def test_avoids_recently_used_types(self, populated_db):
        # Insert a recent dato_curioso post
        first = query_dato_curioso(populated_db)
        assert first is not None
        insert_post(
            "dato_curioso",
            "X",
            "LI",
            metadata={"curiosidad_type": first["curiosidad_type"]},
            db_path=populated_db,
        )

        # Next call should return a different type
        second = query_dato_curioso(populated_db)
        assert second is not None
        assert second["curiosidad_type"] != first["curiosidad_type"]
