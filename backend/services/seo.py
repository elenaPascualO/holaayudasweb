"""Server-side SEO meta tag injection for crawlers and social media previews.

Reads the Vite-built index.html once at startup and replaces meta tags
dynamically for each request based on the URL path.
"""

import json
import logging
import re
from pathlib import Path

from backend.services.convocatorias_db import get_convocatoria_detail_local

logger = logging.getLogger(__name__)

_index_template: str = ""

# Static page SEO config: path -> {title, description}
_STATIC_PAGES: dict[str, dict[str, str]] = {
    "/": {
        "title": "Hola Ayudas - Busca ayudas y subvenciones publicas",
        "description": "Busca ayudas y subvenciones publicas en España de forma facil y rapida. Interfaz moderna para la Base de Datos Nacional de Subvenciones (BDNS). Gratis y sin registro.",
    },
    "/buscar": {
        "title": "Buscar ayudas y subvenciones | Hola Ayudas",
        "description": "Busca ayudas y subvenciones publicas en España. Filtra por tipo de administracion, region, fecha, finalidad y mas.",
    },
    "/datos": {
        "title": "Datos y estadisticas de subvenciones publicas | Hola Ayudas",
        "description": "Dashboard con datos y estadisticas de subvenciones publicas en España. Tendencias, presupuestos, regiones y tematicas.",
    },
    "/transparencia": {
        "title": "Transparencia - Mayores beneficiarios de subvenciones | Hola Ayudas",
        "description": "Ranking de los mayores beneficiarios de subvenciones publicas en España. Consulta quien recibe mas fondos publicos.",
    },
    "/contacto": {
        "title": "Contacto | Hola Ayudas",
        "description": "Contacta con el equipo de Hola Ayudas. Sugerencias, errores o colaboraciones.",
    },
    "/concesiones": {
        "title": "Concesiones de subvenciones | Hola Ayudas",
        "description": "Listado de concesiones de subvenciones publicas otorgadas en España.",
    },
}

BASE_URL = "https://www.holaayudas.com"
DEFAULT_IMAGE = f"{BASE_URL}/og-image.jpg"


def load_index_template(frontend_dist: Path) -> None:
    """Read index.html from the built frontend into memory.

    Args:
        frontend_dist: Path to frontend/dist directory.
    """
    global _index_template
    index_path = frontend_dist / "index.html"
    if index_path.exists():
        _index_template = index_path.read_text(encoding="utf-8")
        logger.info("SEO: loaded index.html template (%d bytes)", len(_index_template))
    else:
        logger.warning("SEO: index.html not found at %s", index_path)


def _replace_meta(html: str, attr: str, value: str, content: str) -> str:
    """Replace a meta tag's content attribute in HTML."""
    pattern = rf'(<meta\s+{attr}="{re.escape(value)}"\s+content=")([^"]*?)(")'
    replacement = rf"\g<1>{content}\3"
    new_html = re.sub(pattern, replacement, html)
    if new_html == html:
        # Try reversed attribute order (content before name/property)
        pattern2 = rf'(<meta\s+content=")([^"]*?)("\s+{attr}="{re.escape(value)}")'
        new_html = re.sub(pattern2, rf"\g<1>{content}\3", html)
    return new_html


def _replace_title(html: str, title: str) -> str:
    """Replace the <title> tag content in HTML."""
    return re.sub(r"<title>[^<]*</title>", f"<title>{title}</title>", html)


def _replace_canonical(html: str, url: str) -> str:
    """Replace the canonical link href in HTML."""
    return re.sub(
        r'(<link\s+rel="canonical"\s+href=")[^"]*(")',
        rf"\g<1>{url}\2",
        html,
    )


def _inject_json_ld(html: str, schemas: list[dict]) -> str:
    """Inject JSON-LD scripts before </head>."""
    scripts = ""
    for schema in schemas:
        scripts += f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>\n'
    return html.replace("</head>", f"{scripts}</head>")


def _build_grant_json_ld(grant: dict, bdns_code: str) -> list[dict]:
    """Build JSON-LD schemas for a grant detail page."""
    organo = grant.get("organo") or {}
    org_name = " - ".join(
        p for p in [organo.get("nivel3"), organo.get("nivel2"), organo.get("nivel1")] if p
    )

    service_schema: dict = {
        "@context": "https://schema.org",
        "@type": "GovernmentService",
        "name": grant.get("descripcion", ""),
        "serviceType": "Subvencion publica",
        "provider": {
            "@type": "GovernmentOrganization",
            "name": org_name,
        },
    }

    if grant.get("descripcionFinalidad"):
        service_schema["category"] = grant["descripcionFinalidad"]

    if grant.get("presupuestoTotal"):
        service_schema["offers"] = {
            "@type": "Offer",
            "price": grant["presupuestoTotal"],
            "priceCurrency": "EUR",
        }

    if grant.get("fechaFinSolicitud"):
        service_schema["availableThrough"] = grant["fechaFinSolicitud"]

    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Inicio", "item": f"{BASE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Buscar", "item": f"{BASE_URL}/buscar"},
            {
                "@type": "ListItem",
                "position": 3,
                "name": grant.get("descripcion", f"Ayuda {bdns_code}"),
                "item": f"{BASE_URL}/ayuda/{bdns_code}",
            },
        ],
    }

    return [service_schema, breadcrumb_schema]


def get_index_html_with_meta(filename: str) -> str | None:
    """Return index.html with SEO meta tags injected based on the URL path.

    Args:
        filename: Request path (e.g., "ayuda/886707" or "").

    Returns:
        HTML string with injected meta tags, or None if template not loaded.
    """
    if not _index_template:
        return None

    path = f"/{filename}" if filename else "/"
    html = _index_template

    # Check for grant detail pages: /ayuda/{bdnsCode}
    grant_match = re.match(r"^/ayuda/(\d+)$", path)
    if grant_match:
        bdns_code = grant_match.group(1)
        grant = get_convocatoria_detail_local(bdns_code)
        if grant:
            organo = grant.get("organo") or {}
            org_name = " - ".join(
                p for p in [organo.get("nivel3"), organo.get("nivel2"), organo.get("nivel1")] if p
            )
            desc_text = (grant.get("descripcion") or "")[:160]
            description = f"{desc_text}" + (f" — {org_name}" if org_name else "")
            title = f"{grant.get('descripcion', f'Ayuda {bdns_code}')} | Hola Ayudas"
            url = f"{BASE_URL}/ayuda/{bdns_code}"

            html = _replace_title(html, title)
            html = _replace_meta(html, "name", "description", description)
            html = _replace_canonical(html, url)

            # OG
            html = _replace_meta(html, "property", "og:title", title)
            html = _replace_meta(html, "property", "og:description", description)
            html = _replace_meta(html, "property", "og:url", url)

            # Twitter
            html = _replace_meta(html, "name", "twitter:title", title)
            html = _replace_meta(html, "name", "twitter:description", description)

            # JSON-LD
            schemas = _build_grant_json_ld(grant, bdns_code)
            html = _inject_json_ld(html, schemas)

            return html

        # Grant not found in local DB — still set basic meta
        title = f"Ayuda {bdns_code} | Hola Ayudas"
        url = f"{BASE_URL}/ayuda/{bdns_code}"
        html = _replace_title(html, title)
        html = _replace_meta(html, "property", "og:title", title)
        html = _replace_meta(html, "property", "og:url", url)
        html = _replace_meta(html, "name", "twitter:title", title)
        html = _replace_canonical(html, url)
        return html

    # Static pages
    # Normalize path: strip trailing slash for lookup (except root)
    lookup_path = path.rstrip("/") or "/"
    page_config = _STATIC_PAGES.get(lookup_path)
    if page_config:
        title = page_config["title"]
        description = page_config["description"]
        url = f"{BASE_URL}{lookup_path}"

        html = _replace_title(html, title)
        html = _replace_meta(html, "name", "description", description)
        html = _replace_canonical(html, url)
        html = _replace_meta(html, "property", "og:title", title)
        html = _replace_meta(html, "property", "og:description", description)
        html = _replace_meta(html, "property", "og:url", url)
        html = _replace_meta(html, "name", "twitter:title", title)
        html = _replace_meta(html, "name", "twitter:description", description)

    return html
