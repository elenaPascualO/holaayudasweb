"""Tests for server-side SEO body injection (seo.py)."""

from unittest.mock import patch

import pytest

from backend.services.seo import (
    _build_grant_body_html,
    _esc,
    _format_currency_es,
    _format_date_es,
    _inject_body_content,
    get_index_html_with_meta,
)


# ---------------------------------------------------------------------------
# _esc
# ---------------------------------------------------------------------------

class TestEsc:
    def test_escapes_html_entities(self):
        assert _esc('<script>alert("xss")</script>') == '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'

    def test_escapes_ampersand(self):
        assert _esc("Ayudas & Subvenciones") == "Ayudas &amp; Subvenciones"

    def test_empty_string(self):
        assert _esc("") == ""

    def test_plain_text_unchanged(self):
        assert _esc("Texto normal sin caracteres especiales") == "Texto normal sin caracteres especiales"


# ---------------------------------------------------------------------------
# _format_currency_es
# ---------------------------------------------------------------------------

class TestFormatCurrencyEs:
    def test_large_amount(self):
        assert _format_currency_es(1500000.50) == "1.500.000,50 EUR"

    def test_zero(self):
        assert _format_currency_es(0) == "0,00 EUR"

    def test_small_amount(self):
        assert _format_currency_es(99.9) == "99,90 EUR"

    def test_integer(self):
        assert _format_currency_es(5000) == "5.000,00 EUR"

    def test_none_returns_none(self):
        assert _format_currency_es(None) is None


# ---------------------------------------------------------------------------
# _format_date_es
# ---------------------------------------------------------------------------

class TestFormatDateEs:
    def test_standard_date(self):
        assert _format_date_es("2026-03-15") == "15 de marzo de 2026"

    def test_january(self):
        assert _format_date_es("2026-01-01") == "1 de enero de 2026"

    def test_december(self):
        assert _format_date_es("2025-12-31") == "31 de diciembre de 2025"

    def test_none_returns_none(self):
        assert _format_date_es(None) is None

    def test_empty_returns_none(self):
        assert _format_date_es("") is None

    def test_datetime_string_uses_date_part(self):
        assert _format_date_es("2026-06-15T10:30:00") == "15 de junio de 2026"

    def test_invalid_returns_raw(self):
        assert _format_date_es("not-a-date") == "not-a-date"


# ---------------------------------------------------------------------------
# _inject_body_content
# ---------------------------------------------------------------------------

class TestInjectBodyContent:
    def test_replaces_single_line(self):
        html = '<div id="app"><h1>Old</h1></div>'
        result = _inject_body_content(html, "<p>New</p>")
        assert result == '<div id="app"><p>New</p></div>'

    def test_replaces_multiline(self):
        html = '<div id="app">\n  <h1>Hola Ayudas</h1>\n</div>'
        result = _inject_body_content(html, "<article>X</article>")
        assert result == '<div id="app"><article>X</article></div>'

    def test_preserves_surrounding_html(self):
        html = '<head></head><body><div id="app"><h1>X</h1></div><script></script></body>'
        result = _inject_body_content(html, "<p>Y</p>")
        assert '<head></head>' in result
        assert '<script></script>' in result
        assert '<div id="app"><p>Y</p></div>' in result

    def test_only_replaces_first_match(self):
        html = '<div id="app">A</div><div id="app">B</div>'
        result = _inject_body_content(html, "C")
        assert result == '<div id="app">C</div><div id="app">B</div>'


# ---------------------------------------------------------------------------
# _build_grant_body_html
# ---------------------------------------------------------------------------

def _make_grant(**overrides) -> dict:
    """Create a grant dict with sensible defaults."""
    base = {
        "descripcion": "Subvenciones para PYMES",
        "organo": {"nivel1": "ESTADO", "nivel2": "Ministerio", "nivel3": "DG"},
        "presupuestoTotal": 50000,
        "descripcionFinalidad": "Empleo",
        "fechaRecepcion": "2026-01-10",
        "fechaInicioSolicitud": "2026-02-01",
        "fechaFinSolicitud": "2026-06-30",
        "tipoConvocatoria": "Concurrencia competitiva",
        "regiones": [{"descripcion": "Toda España"}],
        "tiposBeneficiarios": [{"descripcion": "PYMES"}],
        "descripcionBasesReguladoras": "BOE 2026-01-05",
    }
    base.update(overrides)
    return base


class TestBuildGrantBodyHtml:
    def test_contains_title_in_h1(self):
        html = _build_grant_body_html(_make_grant(), "123")
        assert "<h1>Subvenciones para PYMES</h1>" in html

    def test_contains_organism(self):
        html = _build_grant_body_html(_make_grant(), "123")
        assert "DG · Ministerio · ESTADO" in html

    def test_contains_budget(self):
        html = _build_grant_body_html(_make_grant(), "123")
        assert "50.000,00 EUR" in html

    def test_contains_dates(self):
        html = _build_grant_body_html(_make_grant(), "123")
        assert "10 de enero de 2026" in html
        assert "30 de junio de 2026" in html

    def test_contains_regions(self):
        html = _build_grant_body_html(_make_grant(), "123")
        assert "<li>Toda España</li>" in html

    def test_contains_beneficiaries(self):
        html = _build_grant_body_html(_make_grant(), "123")
        assert "<li>PYMES</li>" in html

    def test_contains_bdns_code(self):
        html = _build_grant_body_html(_make_grant(), "886707")
        assert "886707" in html

    def test_contains_noscript(self):
        html = _build_grant_body_html(_make_grant(), "123")
        assert "<noscript>" in html

    def test_wraps_in_article(self):
        html = _build_grant_body_html(_make_grant(), "123")
        assert html.startswith("<article>")
        assert html.endswith("</article>")

    def test_escapes_html_in_title(self):
        grant = _make_grant(descripcion='Ayudas <script>alert("xss")</script>')
        html = _build_grant_body_html(grant, "123")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_missing_optional_fields(self):
        """Grant with only required fields should not crash."""
        minimal = {
            "descripcion": "Ayuda minima",
            "organo": None,
            "presupuestoTotal": None,
            "descripcionFinalidad": None,
            "fechaRecepcion": None,
            "fechaInicioSolicitud": None,
            "fechaFinSolicitud": None,
            "tipoConvocatoria": None,
            "regiones": [],
            "tiposBeneficiarios": [],
            "descripcionBasesReguladoras": None,
        }
        html = _build_grant_body_html(minimal, "999")
        assert "<h1>Ayuda minima</h1>" in html
        # No crash, no empty sections
        assert "<h2>Regiones</h2>" not in html
        assert "<h2>Beneficiarios</h2>" not in html

    def test_no_organism_section_when_empty(self):
        grant = _make_grant(organo={"nivel1": None, "nivel2": None, "nivel3": None})
        html = _build_grant_body_html(grant, "123")
        # Should not have an empty <p></p> for organism
        assert "<p></p>" not in html


# ---------------------------------------------------------------------------
# get_index_html_with_meta — status codes & error handling
# ---------------------------------------------------------------------------

# Minimal HTML template matching the structure of the real index.html
_FAKE_TEMPLATE = (
    "<!DOCTYPE html><html><head>"
    '<title>Hola Ayudas</title>'
    '<meta name="description" content="default">'
    '<meta name="robots" content="index, follow">'
    '<link rel="canonical" href="https://www.holaayudas.com/">'
    '<meta property="og:title" content="default">'
    '<meta property="og:description" content="default">'
    '<meta property="og:url" content="https://www.holaayudas.com/">'
    '<meta name="twitter:title" content="default">'
    '<meta name="twitter:description" content="default">'
    "</head><body>"
    '<div id="app"><h1>Hola Ayudas</h1></div>'
    "</body></html>"
)


class TestGetIndexHtmlWithMetaStatusCodes:
    """Tests for HTTP status codes and error handling in get_index_html_with_meta."""

    def setup_method(self):
        """Load fake template into module-level variable."""
        import backend.services.seo as seo_mod
        self._original = seo_mod._index_template
        seo_mod._index_template = _FAKE_TEMPLATE

    def teardown_method(self):
        import backend.services.seo as seo_mod
        seo_mod._index_template = self._original

    def test_returns_none_when_no_template(self):
        import backend.services.seo as seo_mod
        seo_mod._index_template = ""
        assert get_index_html_with_meta("ayuda/123") is None

    def test_grant_found_returns_200(self):
        grant = _make_grant()
        with patch("backend.services.seo.get_convocatoria_detail_local", return_value=grant):
            result = get_index_html_with_meta("ayuda/123456")
        assert result is not None
        html, status = result
        assert status == 200
        assert "Subvenciones para PYMES" in html

    def test_grant_not_found_returns_404(self):
        with patch("backend.services.seo.get_convocatoria_detail_local", return_value=None):
            result = get_index_html_with_meta("ayuda/999999")
        assert result is not None
        html, status = result
        assert status == 404
        assert "noindex" in html
        assert "Ayuda no encontrada" in html

    def test_grant_not_found_body_contains_bdns_code(self):
        with patch("backend.services.seo.get_convocatoria_detail_local", return_value=None):
            html, _ = get_index_html_with_meta("ayuda/777777")
        assert "777777" in html

    def test_db_exception_returns_404(self):
        """DB errors should be caught and treated as not-found, not crash with 5xx."""
        with patch("backend.services.seo.get_convocatoria_detail_local", side_effect=Exception("DB locked")):
            result = get_index_html_with_meta("ayuda/123456")
        assert result is not None
        html, status = result
        assert status == 404
        assert "noindex" in html

    def test_static_page_returns_200(self):
        result = get_index_html_with_meta("")
        assert result is not None
        html, status = result
        assert status == 200
        assert "Hola Ayudas" in html

    def test_unknown_route_returns_200(self):
        result = get_index_html_with_meta("unknown/path")
        assert result is not None
        html, status = result
        assert status == 200
