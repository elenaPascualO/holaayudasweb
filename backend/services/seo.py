"""Server-side SEO meta/body injection for crawlers and social media previews.

Reads the Vite-built index.html once at startup and replaces meta tags
and body content dynamically for each request based on the URL path.
For grant detail pages, injects a semantic HTML summary so Google can
index the content without executing JavaScript.
"""

import html as html_module
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
        "description": "Busca ayudas y subvenciones publicas en España de forma facil y rapida. Interfaz moderna para la Base de Datos Nacional de Subvenciones (BDNS).",
    },
    "/buscar": {
        "title": "Buscar ayudas y subvenciones | Hola Ayudas",
        "description": "Busca ayudas y subvenciones publicas en España. Filtra por tipo de administracion, region, fecha, finalidad y mas.",
    },
    "/estadisticas": {
        "title": "Datos y estadisticas de subvenciones publicas | Hola Ayudas",
        "description": "Dashboard con datos y estadisticas de subvenciones publicas en España. Tendencias, presupuestos, regiones y tematicas.",
    },
    "/beneficiarios": {
        "title": "Beneficiarios - Mayores receptores de subvenciones | Hola Ayudas",
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


def _build_static_json_ld(path: str, title: str, description: str) -> list[dict]:
    """Build JSON-LD schemas for static pages."""
    schemas: list[dict] = []

    if path == "/":
        # Homepage: WebSite with SearchAction (enables Bing/Google sitelinks search box)
        schemas.append({
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Hola Ayudas",
            "url": BASE_URL,
            "description": description,
            "potentialAction": {
                "@type": "SearchAction",
                "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": f"{BASE_URL}/buscar?q={{search_term_string}}",
                },
                "query-input": "required name=search_term_string",
            },
        })
    else:
        # Other static pages: WebPage + BreadcrumbList
        schemas.append({
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": title,
            "description": description,
            "url": f"{BASE_URL}{path}",
            "isPartOf": {"@type": "WebSite", "name": "Hola Ayudas", "url": BASE_URL},
        })
        schemas.append({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Inicio", "item": f"{BASE_URL}/"},
                {"@type": "ListItem", "position": 2, "name": title.split("|")[0].strip(), "item": f"{BASE_URL}{path}"},
            ],
        })

    return schemas


def _esc(text: str) -> str:
    """HTML-escape a string."""
    return html_module.escape(text, quote=True)


def _format_currency_es(amount: float | int | None) -> str | None:
    """Format a number as Spanish currency (e.g. 1.500.000,00 EUR)."""
    if amount is None:
        return None
    # Format with 2 decimals, then swap separators to Spanish style
    formatted = f"{amount:,.2f}"
    # "1,500,000.00" → "1.500.000,00"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} EUR"


def _format_date_es(date_str: str | None) -> str | None:
    """Format an ISO date (YYYY-MM-DD) to Spanish (e.g. '15 de marzo de 2026')."""
    if not date_str:
        return None
    months = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    try:
        parts = date_str[:10].split("-")
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{day} de {months[month - 1]} de {year}"
    except (ValueError, IndexError):
        return date_str


def _build_grant_body_html(grant: dict, bdns_code: str) -> str:
    """Build a semantic HTML summary of a grant for server-side body injection.

    This content is visible to crawlers (Google, Bing) without JS execution.
    The frontend JS replaces it with the interactive version on load.
    """
    parts: list[str] = ['<article>']

    # Title
    titulo = _esc(grant.get("descripcion") or f"Ayuda {bdns_code}")
    parts.append(f"<h1>{titulo}</h1>")

    # Organism
    organo = grant.get("organo") or {}
    org_parts = [p for p in [organo.get("nivel3"), organo.get("nivel2"), organo.get("nivel1")] if p]
    if org_parts:
        parts.append(f'<p>{_esc(" · ".join(org_parts))}</p>')

    # Key facts as definition list
    parts.append("<dl>")
    if grant.get("presupuestoTotal"):
        budget = _format_currency_es(grant["presupuestoTotal"])
        parts.append(f"<dt>Presupuesto</dt><dd>{_esc(budget)}</dd>")
    if grant.get("descripcionFinalidad"):
        parts.append(f'<dt>Finalidad</dt><dd>{_esc(grant["descripcionFinalidad"])}</dd>')
    if grant.get("fechaRecepcion"):
        fecha = _format_date_es(grant["fechaRecepcion"])
        if fecha:
            parts.append(f"<dt>Fecha publicacion</dt><dd>{_esc(fecha)}</dd>")
    if grant.get("fechaInicioSolicitud"):
        fecha = _format_date_es(grant["fechaInicioSolicitud"])
        if fecha:
            parts.append(f"<dt>Inicio solicitudes</dt><dd>{_esc(fecha)}</dd>")
    if grant.get("fechaFinSolicitud"):
        fecha = _format_date_es(grant["fechaFinSolicitud"])
        if fecha:
            parts.append(f"<dt>Fin solicitudes</dt><dd>{_esc(fecha)}</dd>")
    if grant.get("tipoConvocatoria"):
        parts.append(f'<dt>Tipo</dt><dd>{_esc(grant["tipoConvocatoria"])}</dd>')
    parts.append("</dl>")

    # Regions
    regiones = grant.get("regiones") or []
    if regiones:
        names = [r.get("descripcion") or "" for r in regiones if r.get("descripcion")]
        if names:
            items = "".join(f"<li>{_esc(n)}</li>" for n in names)
            parts.append(f"<h2>Regiones</h2><ul>{items}</ul>")

    # Beneficiary types
    beneficiarios = grant.get("tiposBeneficiarios") or []
    if beneficiarios:
        names = [b.get("descripcion") or "" for b in beneficiarios if b.get("descripcion")]
        if names:
            items = "".join(f"<li>{_esc(n)}</li>" for n in names)
            parts.append(f"<h2>Beneficiarios</h2><ul>{items}</ul>")

    # Bases reguladoras
    if grant.get("descripcionBasesReguladoras"):
        parts.append(f'<h2>Bases reguladoras</h2><p>{_esc(grant["descripcionBasesReguladoras"])}</p>')

    parts.append(f'<p>Codigo BDNS: {_esc(bdns_code)}</p>')
    parts.append('<noscript><p>Activa JavaScript para usar todas las funciones de Hola Ayudas.</p></noscript>')
    parts.append("</article>")

    return "\n".join(parts)


def _inject_body_content(html: str, body_html: str) -> str:
    """Replace the content inside <div id="app">...</div> with server-rendered HTML."""
    return re.sub(
        r'(<div id="app">).*?(</div>)',
        rf"\1{body_html}\2",
        html,
        count=1,
        flags=re.DOTALL,
    )


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

            # Server-side body content for crawlers
            body_html = _build_grant_body_html(grant, bdns_code)
            html = _inject_body_content(html, body_html)

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

        # JSON-LD structured data
        schemas = _build_static_json_ld(lookup_path, title, description)
        html = _inject_json_ld(html, schemas)

        # Inject H1 for crawlers that don't execute JS
        page_h1 = title.split("|")[0].split(" - ")[0].strip()
        body_html = f"<h1>{_esc(page_h1)}</h1><p>{_esc(description)}</p>"
        html = _inject_body_content(html, body_html)
    else:
        # Unknown route — still set canonical to the clean path (no query params)
        url = f"{BASE_URL}{lookup_path}"
        html = _replace_canonical(html, url)
        html = _replace_meta(html, "property", "og:url", url)

    return html
