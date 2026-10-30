"""Tests for frontend/public/robots.txt crawler policy.

Parsed with urllib.robotparser, which (like Google and RFC 9309) applies the
most specific matching rule.
"""

from pathlib import Path
from urllib.robotparser import RobotFileParser

import pytest

ROBOTS_PATH = Path(__file__).resolve().parents[2] / "frontend" / "public" / "robots.txt"
SITE = "https://www.holaayudas.com"
PAGES = ["/", "/ayuda/123", "/buscar", "/sitemap.xml"]


@pytest.fixture(scope="module")
def robots() -> RobotFileParser:
    parser = RobotFileParser()
    parser.parse(ROBOTS_PATH.read_text().splitlines())
    return parser


@pytest.mark.parametrize("agent", ["Googlebot", "Bingbot", "Applebot", "DuckDuckBot"])
def test_search_engines_can_crawl_pages(robots, agent):
    for page in PAGES:
        assert robots.can_fetch(agent, SITE + page), f"{agent} blocked from {page}"


@pytest.mark.parametrize("agent", [
    "AhrefsBot", "SemrushBot", "PetalBot", "AwarioBot",
    "MJ12bot", "DotBot", "BLEXBot", "DataForSeoBot",
])
def test_seo_crawlers_blocked(robots, agent):
    for page in ("/", "/ayuda/123"):
        assert not robots.can_fetch(agent, SITE + page), f"{agent} allowed on {page}"


@pytest.mark.parametrize("agent", [
    "GPTBot", "OAI-SearchBot", "ClaudeBot", "Claude-SearchBot",
    "PerplexityBot", "Google-Extended", "CCBot",
])
def test_ai_bots_allowed(robots, agent):
    """Decision A: AI bots may crawl (and cite) grant pages."""
    assert robots.can_fetch(agent, SITE + "/ayuda/123")


@pytest.mark.parametrize("agent", ["Googlebot", "Bingbot", "GPTBot", "*"])
def test_api_disallowed_for_everyone(robots, agent):
    assert not robots.can_fetch(agent, SITE + "/api/convocatorias")


def test_sitemap_declared(robots):
    assert robots.site_maps() == [f"{SITE}/sitemap.xml"]
