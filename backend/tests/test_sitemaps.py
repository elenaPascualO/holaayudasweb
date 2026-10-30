"""Tests for pregenerated sitemaps (services/sitemaps.py)."""

import gzip
import json
import os
import re
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.config import SITE_BASE_URL
from backend.services import sitemaps
from backend.services.convocatorias_db import init_convocatorias_db, upsert_convocatorias_list

CURRENT_YEAR = datetime.now(timezone.utc).year
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


def _insert(db_path: str, numero: str, recepcion: str, fin: str | None, updated: str) -> None:
    """Insert a convocatoria with detail fetched and explicit dates."""
    upsert_convocatorias_list([{
        "numeroConvocatoria": numero,
        "descripcion": f"Convocatoria {numero}",
        "fechaRecepcion": recepcion,
        "organo": {"nivel1": "ESTADO", "nivel2": "MIN", "nivel3": None},
    }], db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """UPDATE convocatorias
           SET detail_fetched = 1, fecha_recepcion = ?, fecha_fin_solicitud = ?, updated_at = ?
           WHERE numero_convocatoria = ?""",
        (recepcion, fin, updated, numero),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def db_path(tmp_path):
    """DB with open grants, closed grants in 2023 (3) and 2024 (1), and one closed this year."""
    path = str(tmp_path / "sitemaps.db")
    init_convocatorias_db(path)

    _insert(path, "OPEN1", "2025-05-01", "2099-12-31", "2026-10-01 10:00:00")
    _insert(path, "OPEN2", "2025-06-01", None, "2026-10-02 10:00:00")
    _insert(path, "C2023A", "2023-01-10", "2023-03-01", "2023-03-02 10:00:00")
    _insert(path, "C2023B", "2023-02-10", "2023-04-01", "2023-04-02 10:00:00")
    _insert(path, "C2023C", "2023-03-10", "2023-05-01", "2023-05-02 10:00:00")
    _insert(path, "C2024A", "2024-01-10", "2024-03-01", "2024-03-02 10:00:00")
    _insert(path, "CCUR", f"{CURRENT_YEAR}-01-01", YESTERDAY, f"{CURRENT_YEAR}-01-05 10:00:00")
    return path


@pytest.fixture
def out_dir(tmp_path):
    return str(tmp_path / "sitemaps")


def _read(out_dir: str, filename: str) -> str:
    with open(os.path.join(out_dir, filename), "rb") as f:
        return gzip.decompress(f.read()).decode("utf-8")


def _gz_files(out_dir: str) -> set[str]:
    return {f for f in os.listdir(out_dir) if f.endswith(".xml.gz")}


def _index_locs(out_dir: str) -> set[str]:
    index = _read(out_dir, "sitemap.xml.gz")
    return set(re.findall(r"<loc>([^<]+)</loc>", index))


class TestGenerateAll:
    """Generation of every sitemap file to disk."""

    def test_generate_writes_all_files(self, db_path, out_dir):
        result = sitemaps.generate_all(db_path=db_path, out_dir=out_dir)

        assert result["status"] == "completed"
        assert _gz_files(out_dir) == {
            "sitemap.xml.gz",
            "sitemap-static.xml.gz",
            "sitemap-grants-open-1.xml.gz",
            "sitemap-grants-closed-2023.xml.gz",
            "sitemap-grants-closed-2024.xml.gz",
            f"sitemap-grants-closed-{CURRENT_YEAR}.xml.gz",
        }
        assert result["files"] == 6
        assert result["urls"] == 7 + len(sitemaps.STATIC_PAGES)

    def test_index_lists_exactly_generated_files(self, db_path, out_dir):
        sitemaps.generate_all(db_path=db_path, out_dir=out_dir)

        expected = {
            f"{SITE_BASE_URL}/{name[:-3]}"
            for name in _gz_files(out_dir)
            if name != "sitemap.xml.gz"
        }
        assert _index_locs(out_dir) == expected

    def test_open_sitemap_contains_open_grants_only(self, db_path, out_dir):
        sitemaps.generate_all(db_path=db_path, out_dir=out_dir)

        open_xml = _read(out_dir, "sitemap-grants-open-1.xml.gz")
        assert f"{SITE_BASE_URL}/ayuda/OPEN1" in open_xml
        assert f"{SITE_BASE_URL}/ayuda/OPEN2" in open_xml
        assert "C2023A" not in open_xml

        closed_xml = _read(out_dir, "sitemap-grants-closed-2023.xml.gz")
        assert "OPEN1" not in closed_xml
        assert all(f"/ayuda/{n}" in closed_xml for n in ("C2023A", "C2023B", "C2023C"))

    def test_closed_sitemaps_split_by_year_and_page(self, db_path, out_dir, monkeypatch):
        monkeypatch.setattr(sitemaps, "_GRANTS_PER_SITEMAP", 2)
        sitemaps.generate_all(db_path=db_path, out_dir=out_dir)

        files = _gz_files(out_dir)
        assert "sitemap-grants-closed-2023.xml.gz" in files
        assert "sitemap-grants-closed-2023-2.xml.gz" in files
        assert "sitemap-grants-closed-2023-3.xml.gz" not in files

        page1 = _read(out_dir, "sitemap-grants-closed-2023.xml.gz")
        page2 = _read(out_dir, "sitemap-grants-closed-2023-2.xml.gz")
        assert page1.count("<url>") == 2
        assert page2.count("<url>") == 1
        assert f"{SITE_BASE_URL}/sitemap-grants-closed-2023-2.xml" in _index_locs(out_dir)

    def test_xml_content_unchanged(self, db_path, out_dir):
        """Same XML structure and values as the former on-demand generation."""
        sitemaps.generate_all(db_path=db_path, out_dir=out_dir)

        open_xml = _read(out_dir, "sitemap-grants-open-1.xml.gz")
        assert open_xml.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<urlset')
        assert (
            f"  <url>\n    <loc>{SITE_BASE_URL}/ayuda/OPEN1</loc>\n"
            "    <lastmod>2026-10-01</lastmod>\n"
            "    <changefreq>weekly</changefreq>\n"
            "    <priority>0.8</priority>\n  </url>"
        ) in open_xml
        # Ordered by fecha_recepcion DESC
        assert open_xml.index("OPEN2") < open_xml.index("OPEN1")

        past = _read(out_dir, "sitemap-grants-closed-2024.xml.gz")
        assert "<changefreq>yearly</changefreq>" in past
        assert "<priority>0.3</priority>" in past

        current = _read(out_dir, f"sitemap-grants-closed-{CURRENT_YEAR}.xml.gz")
        assert "<changefreq>monthly</changefreq>" in current
        assert "<priority>0.4</priority>" in current

        static = _read(out_dir, "sitemap-static.xml.gz")
        for page in sitemaps.STATIC_PAGES:
            assert f"<loc>{SITE_BASE_URL}{page['loc']}</loc>" in static

        index = _read(out_dir, "sitemap.xml.gz")
        assert "<sitemapindex" in index
        assert (
            f"    <loc>{SITE_BASE_URL}/sitemap-grants-closed-2023.xml</loc>\n"
            "    <lastmod>2023-05-02</lastmod>"
        ) in index

    def test_builders_match_generated_files(self, db_path, out_dir):
        """On-demand builders (route fallback) produce the same XML as the files."""
        sitemaps.generate_all(db_path=db_path, out_dir=out_dir)

        assert _read(out_dir, "sitemap-grants-open-1.xml.gz") == sitemaps.build_open_xml(
            1, db_path=db_path
        )
        assert _read(out_dir, "sitemap-grants-closed-2023.xml.gz") == sitemaps.build_closed_xml(
            "2023", 1, db_path=db_path
        )
        assert _read(out_dir, "sitemap-static.xml.gz") == sitemaps.build_static_xml()

    def test_removes_stale_files(self, db_path, out_dir, monkeypatch):
        monkeypatch.setattr(sitemaps, "_GRANTS_PER_SITEMAP", 2)
        sitemaps.generate_all(db_path=db_path, out_dir=out_dir)
        assert "sitemap-grants-closed-2023-2.xml.gz" in _gz_files(out_dir)

        monkeypatch.setattr(sitemaps, "_GRANTS_PER_SITEMAP", 50_000)
        sitemaps.generate_all(db_path=db_path, out_dir=out_dir)
        assert "sitemap-grants-closed-2023-2.xml.gz" not in _gz_files(out_dir)

    def test_no_tmp_files_left(self, db_path, out_dir):
        sitemaps.generate_all(db_path=db_path, out_dir=out_dir)
        assert not [f for f in os.listdir(out_dir) if f.endswith(".tmp")]

    def test_concurrent_generation_skipped(self, db_path, out_dir):
        with sitemaps._gen_lock:
            assert sitemaps.is_generating() is True
            result = sitemaps.generate_all(db_path=db_path, out_dir=out_dir)

        assert result["status"] == "skipped"
        assert not os.path.exists(out_dir) or not _gz_files(out_dir)
        assert sitemaps.is_generating() is False


class TestRegenerationState:
    """needs_regeneration / get_status / read_sitemap."""

    def test_needs_regeneration(self, db_path, out_dir):
        assert sitemaps.needs_regeneration(out_dir=out_dir) is True

        sitemaps.generate_all(db_path=db_path, out_dir=out_dir)
        assert sitemaps.needs_regeneration(out_dir=out_dir) is False

        # Make the generation look 25 hours old
        meta_path = os.path.join(out_dir, sitemaps.META_FILENAME)
        with open(meta_path) as f:
            meta = json.load(f)
        old = datetime.now(timezone.utc) - timedelta(hours=25)
        meta["generated_at"] = old.isoformat()
        with open(meta_path, "w") as f:
            json.dump(meta, f)
        assert sitemaps.needs_regeneration(out_dir=out_dir) is True

    def test_needs_regeneration_when_index_missing(self, db_path, out_dir):
        sitemaps.generate_all(db_path=db_path, out_dir=out_dir)
        os.remove(os.path.join(out_dir, "sitemap.xml.gz"))
        assert sitemaps.needs_regeneration(out_dir=out_dir) is True

    def test_get_status(self, db_path, out_dir):
        status = sitemaps.get_status(out_dir=out_dir)
        assert status["generated_at"] is None
        assert status["generating"] is False

        sitemaps.generate_all(db_path=db_path, out_dir=out_dir)
        status = sitemaps.get_status(out_dir=out_dir)
        assert status["generated_at"] is not None
        assert status["files"] == 6
        assert status["urls"] == 7 + len(sitemaps.STATIC_PAGES)

    def test_read_sitemap(self, db_path, out_dir):
        assert sitemaps.read_sitemap("sitemap.xml", out_dir=out_dir) is None

        sitemaps.generate_all(db_path=db_path, out_dir=out_dir)
        data = sitemaps.read_sitemap("sitemap.xml", out_dir=out_dir)
        assert gzip.decompress(data).decode().startswith('<?xml version="1.0"')

    def test_read_sitemap_rejects_unknown_names(self, db_path, out_dir):
        sitemaps.generate_all(db_path=db_path, out_dir=out_dir)
        assert sitemaps.read_sitemap("../sitemaps.db", out_dir=out_dir) is None
        assert sitemaps.read_sitemap("sitemaps.meta.json", out_dir=out_dir) is None


def test_generation_is_reasonably_fast(db_path, out_dir):
    """Sanity check: tiny DB generates instantly (guards against accidental O(n^2))."""
    start = time.monotonic()
    sitemaps.generate_all(db_path=db_path, out_dir=out_dir)
    assert time.monotonic() - start < 2
