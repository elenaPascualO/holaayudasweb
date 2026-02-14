"""Tests for get_grant_status() logic."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from backend.services.bdns_client import get_grant_status


def _fmt(dt: datetime) -> str:
    """Format datetime as BDNS date string (dd/mm/yyyy)."""
    return dt.strftime("%d/%m/%Y")


@pytest.fixture
def today():
    """Return today at midnight for date comparisons."""
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def test_none_returns_unknown():
    """None grant returns unknown."""
    assert get_grant_status(None) == "unknown"


def test_empty_dict_returns_unknown():
    """Empty grant dict returns unknown."""
    assert get_grant_status({}) == "unknown"


def test_permanent_open_no_end_date():
    """Grant with abierto=True and no end date is permanent."""
    grant = {"abierto": True}
    assert get_grant_status(grant) == "permanent"


def test_permanent_with_start_date(today):
    """Grant with abierto=True, start date, but no end date is permanent."""
    grant = {
        "abierto": True,
        "fechaInicioSolicitud": _fmt(today - timedelta(days=30)),
    }
    assert get_grant_status(grant) == "permanent"


def test_closed_end_date_past(today):
    """Grant with end date in the past is closed."""
    grant = {
        "fechaFinSolicitud": _fmt(today - timedelta(days=1)),
    }
    assert get_grant_status(grant) == "closed"


def test_closed_takes_priority_over_abierto(today):
    """End date in the past means closed even if abierto=True."""
    grant = {
        "abierto": True,
        "fechaFinSolicitud": _fmt(today - timedelta(days=1)),
    }
    assert get_grant_status(grant) == "closed"


def test_upcoming_start_date_future(today):
    """Grant with start date in the future is upcoming."""
    grant = {
        "fechaInicioSolicitud": _fmt(today + timedelta(days=10)),
        "fechaFinSolicitud": _fmt(today + timedelta(days=40)),
    }
    assert get_grant_status(grant) == "upcoming"


def test_open_within_date_range(today):
    """Grant with start in past and end in future is open."""
    grant = {
        "fechaInicioSolicitud": _fmt(today - timedelta(days=10)),
        "fechaFinSolicitud": _fmt(today + timedelta(days=10)),
    }
    assert get_grant_status(grant) == "open"


def test_open_end_date_today(today):
    """Grant with end date today is open (>= comparison)."""
    grant = {
        "fechaFinSolicitud": _fmt(today),
    }
    assert get_grant_status(grant) == "open"


def test_open_end_date_future_no_start(today):
    """Grant with only end date in future is open."""
    grant = {
        "fechaFinSolicitud": _fmt(today + timedelta(days=30)),
    }
    assert get_grant_status(grant) == "open"


def test_open_via_abierto_flag():
    """Grant with abierto=True and end date (but no parseable dates) is open via flag."""
    grant = {
        "abierto": True,
        "fechaFinSolicitud": "invalid-date",
    }
    assert get_grant_status(grant) == "open"


def test_unknown_no_dates_no_flag():
    """Grant with no dates and no abierto flag is unknown."""
    grant = {"descripcion": "Some grant"}
    assert get_grant_status(grant) == "unknown"


def test_uses_text_inicio_fallback(today):
    """Uses textInicio when fechaInicioSolicitud is absent."""
    grant = {
        "textInicio": _fmt(today + timedelta(days=5)),
        "fechaFinSolicitud": _fmt(today + timedelta(days=30)),
    }
    assert get_grant_status(grant) == "upcoming"


def test_uses_text_fin_fallback(today):
    """Uses textFin when fechaFinSolicitud is absent."""
    grant = {
        "textFin": _fmt(today - timedelta(days=1)),
    }
    assert get_grant_status(grant) == "closed"


def _fmt_iso(dt: datetime) -> str:
    """Format datetime as ISO date string (YYYY-MM-DD)."""
    return dt.strftime("%Y-%m-%d")


def test_iso_date_closed(today):
    """Handles ISO format dates (YYYY-MM-DD) correctly."""
    grant = {
        "fechaFinSolicitud": _fmt_iso(today - timedelta(days=1)),
    }
    assert get_grant_status(grant) == "closed"


def test_iso_date_open(today):
    """Handles ISO format dates for open status."""
    grant = {
        "fechaInicioSolicitud": _fmt_iso(today - timedelta(days=5)),
        "fechaFinSolicitud": _fmt_iso(today + timedelta(days=10)),
    }
    assert get_grant_status(grant) == "open"


def test_iso_date_upcoming(today):
    """Handles ISO format dates for upcoming status."""
    grant = {
        "fechaInicioSolicitud": _fmt_iso(today + timedelta(days=5)),
        "fechaFinSolicitud": _fmt_iso(today + timedelta(days=30)),
    }
    assert get_grant_status(grant) == "upcoming"
