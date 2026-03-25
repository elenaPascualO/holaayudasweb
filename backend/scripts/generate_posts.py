"""Generate social media post drafts from convocatorias data.

Usage:
    uv run python -m backend.scripts.generate_posts [post_type]

Post types:
    ayuda_destacada    - Highlight one interesting open grant
    datos_semana       - Weekly stats summary
    cierre_inminente   - Grants closing in next 7 days
    tematico           - Grouped by theme
    top_organismo      - Most active organism this week
    dato_curioso       - Surprising fact from historical data
    auto               - Auto-select based on schedule (default)
"""

import asyncio
import json
import logging
import sys
from datetime import date

from backend.config import OPENAI_API_KEY, POSTS_OPENAI_MODEL
from backend.services.posts_db import (
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
)

logger = logging.getLogger(__name__)

VALID_POST_TYPES = [
    "ayuda_destacada",
    "datos_semana",
    "cierre_inminente",
    "tematico",
    "top_organismo",
    "dato_curioso",
]

SYSTEM_PROMPT = """\
You are a data journalist for HolaDatos, a Spanish public data transparency \
project. You report on government grants and subsidies (ayudas y subvenciones) \
from Spain's BDNS database.

CRITICAL — Objectivity rules (these override everything else):
- You are a DATA REPORTER, not an advocate. Present facts, never opinions.
- NEVER evaluate whether grants are positive, negative, effective, or necessary.
- NEVER use words like: fundamental, esencial, clave, necesario, importante, \
generoso, compromiso, impulso, oportunidad, apoyo, impacto positivo, logro.
- NEVER praise or justify government spending (e.g., "evidencia el compromiso \
del Estado", "herramienta clave para el desarrollo", "esfuerzo significativo").
- NEVER suggest what the reader should think about the data.
- NEVER add interpretive filler about what the data "means" for the economy, \
society, or any sector. If the data doesn't say it, don't write it.
- Stick to: what, how much, who, where, when. Nothing more.

BAD examples (DO NOT write like this):
- "evidenciando el compromiso del Estado con el apoyo a diversos sectores"
- "Las ayudas son una herramienta clave para fomentar el desarrollo económico"
- "refleja un enfoque significativo en la asignación de recursos"
- "invita a reflexionar sobre la dinámica de la financiación pública"
- "el papel que juega en el desarrollo de diferentes sectores"
- "se destacó por su alta inversión"

GOOD examples (write like this):
- "2021 fue el año con mayor presupuesto registrado: 514.800M€ en 57.056 \
convocatorias. Es la cifra más alta de la serie histórica."
- "Barcelona acumula 44.852 convocatorias publicadas, más que cualquier \
otra provincia. Le siguen Valencia (24.121) y Cataluña como comunidad (20.820)."

If you run out of facts to fill the post length, it is BETTER to write a \
shorter post than to pad it with interpretive filler. A 400-char LinkedIn \
post with pure data is better than a 1000-char post with opinions.

Other rules:
- Always write in Spanish
- Use a clear, accessible tone
- Include relevant emojis sparingly (2-4 per post, not at every line)
- Always include a call to action directing to holaayudas.com
- Never invent data — only use the numbers provided
- Format budget amounts in millions/thousands with € symbol \
(e.g. 5M€, 200.000€)
- Do not use markdown formatting (no bold, no links syntax)

You must output valid JSON with exactly two keys:
- "content_x": Post for X/Twitter (200-500 characters, informal, punchy, \
direct, 2-3 hashtags at the end)
- "content_linkedin": Post for LinkedIn (400-1200 characters, professional, \
structured with line breaks, factual context only, 3-5 hashtags at the end). \
Shorter is fine if the data doesn't warrant more.
"""


def _format_budget(amount: float) -> str:
    """Format a budget amount for display in prompts."""
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:.1f} mil M€"
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.1f}M€"
    if amount >= 1_000:
        return f"{amount / 1_000:.0f} mil €"
    return f"{amount:.0f}€"


def build_ayuda_destacada_prompt(grant: dict) -> str:
    """Build user prompt for ayuda_destacada post type."""
    return f"""\
Escribe un post sobre esta ayuda pública destacada:

- Título: {grant['descripcion']}
- Presupuesto: {_format_budget(grant.get('presupuesto_total', 0))}
- Organismo: {grant.get('nivel2', 'No disponible')}
- Temática: {grant.get('descripcion_finalidad', 'General')}
- Plazo: hasta {grant.get('fecha_fin_solicitud', 'sin fecha límite')}
- Enlace: https://www.holaayudas.com/convocatoria/{grant['numero_convocatoria']}

Destaca por qué es interesante (alto presupuesto, temática relevante, \
accesibilidad). Haz que el lector quiera saber más."""


def build_datos_semana_prompt(stats: dict) -> str:
    """Build user prompt for datos_semana post type."""
    return f"""\
Escribe un resumen semanal con estos datos de ayudas públicas en España:

- Nuevas ayudas esta semana: {stats['new_count']}
- Presupuesto total nuevas: {_format_budget(stats['total_budget'])}
- Región más activa: {stats.get('top_region', 'No disponible')}
- Temática más frecuente: {stats.get('top_theme', 'No disponible')}
- Total ayudas abiertas ahora: {stats['total_open']}

Presenta los datos de forma atractiva. Cierra invitando a buscar ayudas \
en https://www.holaayudas.com"""


def build_cierre_inminente_prompt(grants: list[dict]) -> str:
    """Build user prompt for cierre_inminente post type."""
    lines = []
    for g in grants[:5]:
        budget_str = _format_budget(g["presupuesto_total"]) if g.get("presupuesto_total") else "No indicado"
        lines.append(
            f"- {g['descripcion']}\n"
            f"  Presupuesto: {budget_str} | Cierra: {g['fecha_fin_solicitud']}\n"
            f"  Enlace: https://www.holaayudas.com/convocatoria/{g['numero_convocatoria']}"
        )
    grants_text = "\n".join(lines)
    return f"""\
Escribe un post urgente sobre ayudas que cierran esta semana:

{grants_text}

Transmite urgencia sin alarmismo. Anima a consultar antes de que cierren. \
Incluye los enlaces de las más importantes (máximo 2-3 en X, todos en LinkedIn)."""


def build_tematico_prompt(data: dict) -> str:
    """Build user prompt for tematico post type."""
    lines = []
    for g in data["grants"]:
        budget_str = _format_budget(g["presupuesto_total"]) if g.get("presupuesto_total") else "No indicado"
        lines.append(
            f"- {g['descripcion']}\n"
            f"  Presupuesto: {budget_str} | Organismo: {g.get('nivel2', 'N/A')}\n"
            f"  Enlace: https://www.holaayudas.com/convocatoria/{g['numero_convocatoria']}"
        )
    grants_text = "\n".join(lines)
    return f"""\
Escribe un post temático sobre ayudas de "{data['theme']}":

{grants_text}

Agrupa y presenta las ayudas de forma coherente para alguien interesado \
en este tema. Incluye los enlaces más relevantes. Invita a buscar más \
en https://www.holaayudas.com"""


def build_top_organismo_prompt(data: dict) -> str:
    """Build user prompt for top_organismo post type."""
    lines = []
    for g in data["grants"][:3]:
        budget_str = _format_budget(g["presupuesto_total"]) if g.get("presupuesto_total") else "No indicado"
        lines.append(f"- {g['descripcion']} ({budget_str})")
    grants_text = "\n".join(lines)
    return f"""\
Escribe un post sobre el organismo más activo esta semana:

- Organismo: {data['organism']}
- Convocatorias publicadas esta semana: {data['count']}
- Presupuesto total: {_format_budget(data['total_budget'])}

Ejemplos de ayudas publicadas:
{grants_text}

Presenta al organismo y su actividad de forma informativa. \
Enlaza a https://www.holaayudas.com para ver todas sus ayudas."""


def build_dato_curioso_prompt(data: dict) -> str:
    """Build user prompt for dato_curioso post type."""
    curiosidad_type = data["curiosidad_type"]
    d = data["data"]

    descriptions = {
        "mayor_presupuesto_historico": (
            f"La mayor ayuda jamás publicada en España fue:\n"
            f"- Descripción: {d.get('descripcion', 'N/A')}\n"
            f"- Presupuesto: {_format_budget(d.get('presupuesto_total', 0))}\n"
            f"- Organismo: {d.get('nivel2', 'N/A')}\n"
            f"- Año: {d.get('fecha_recepcion', 'N/A')[:4] if d.get('fecha_recepcion') else 'N/A'}"
        ),
        "ano_record": (
            f"El año con más ayudas publicadas fue {d.get('year', 'N/A')} "
            f"con {d.get('cnt', 0):,} convocatorias y un presupuesto total "
            f"de {_format_budget(d.get('budget', 0))}."
        ),
        "ano_record_presupuesto": (
            f"El año con mayor presupuesto en ayudas fue {d.get('year', 'N/A')} "
            f"con {_format_budget(d.get('budget', 0))} repartidos en "
            f"{d.get('cnt', 0):,} convocatorias."
        ),
        "organismo_mas_activo": (
            f"El organismo que más ayudas ha publicado históricamente es "
            f"{d.get('nivel2', 'N/A')} con {d.get('cnt', 0):,} convocatorias "
            f"y un presupuesto acumulado de {_format_budget(d.get('budget', 0))}."
        ),
        "region_mas_ayudas": (
            f"La región con más ayudas publicadas es {d.get('region', 'N/A')} "
            f"con {d.get('cnt', 0):,} convocatorias."
        ),
        "tema_mas_presupuesto": (
            f"La temática con mayor presupuesto acumulado es "
            f"\"{d.get('descripcion_finalidad', 'N/A')}\" con "
            f"{_format_budget(d.get('budget', 0))} en "
            f"{d.get('cnt', 0):,} convocatorias."
        ),
        "media_presupuesto_anual": (
            f"El año con mayor presupuesto medio por ayuda fue "
            f"{d.get('year', 'N/A')} con una media de "
            f"{_format_budget(d.get('avg_budget', 0))} por convocatoria "
            f"({d.get('cnt', 0):,} ayudas con presupuesto)."
        ),
    }

    description = descriptions.get(curiosidad_type, str(d))
    return f"""\
Escribe un post tipo "¿Sabías que...?" con este dato curioso sobre \
ayudas públicas en España:

{description}

Haz que sea sorprendente e interesante. Contextualiza el dato para que \
el lector entienda su importancia. Cierra invitando a explorar más datos \
en https://www.holaayudas.com/estadisticas"""


async def generate_post_content(post_type: str, data: dict) -> dict:
    """Call OpenAI to generate post content.

    Args:
        post_type: The type of post being generated.
        data: The data to include in the prompt.

    Returns:
        Dict with content_x and content_linkedin keys.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    prompt_builders = {
        "ayuda_destacada": build_ayuda_destacada_prompt,
        "datos_semana": build_datos_semana_prompt,
        "cierre_inminente": build_cierre_inminente_prompt,
        "tematico": build_tematico_prompt,
        "top_organismo": build_top_organismo_prompt,
        "dato_curioso": build_dato_curioso_prompt,
    }

    user_prompt = prompt_builders[post_type](data)
    logger.info("Generating %s post with %s...", post_type, POSTS_OPENAI_MODEL)

    response = await client.chat.completions.create(
        model=POSTS_OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=2000,
    )

    result = json.loads(response.choices[0].message.content)
    logger.info(
        "Generated: X=%d chars, LinkedIn=%d chars",
        len(result.get("content_x", "")),
        len(result.get("content_linkedin", "")),
    )
    return result


def select_next_post_type(db_path: str | None = None) -> str:
    """Auto-select next post type based on what was generated least recently.

    Priority:
    1. cierre_inminente — if there are grants closing in 7 days
    2. datos_semana — on Mon-Wed
    3. top_organismo — if notable activity
    4. ayuda_destacada
    5. dato_curioso
    6. tematico — least frequent

    Args:
        db_path: Override path for tests.

    Returns:
        The selected post type string.
    """
    # Check what types have been generated recently (last 7 days)
    recent = list_posts(limit=50, db_path=db_path)
    recent_types = [p["post_type"] for p in recent if p["status"] != "discarded"]

    # Count occurrences in last 7 days
    from datetime import datetime, timedelta

    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    recent_week = [
        p["post_type"] for p in recent
        if p.get("created_at", "") >= cutoff and p["status"] != "discarded"
    ]

    # Priority 1: cierre_inminente if there are grants closing soon
    if "cierre_inminente" not in recent_week:
        closing = query_cierre_inminente(days=7, limit=1, db_path=db_path)
        if closing:
            return "cierre_inminente"

    # Priority 2: datos_semana on Mon-Wed
    weekday = date.today().weekday()  # 0=Mon, 6=Sun
    if weekday <= 2 and "datos_semana" not in recent_week:
        return "datos_semana"

    # Priority 3: top_organismo
    if "top_organismo" not in recent_week:
        org = query_top_organismo(db_path=db_path)
        if org:
            return "top_organismo"

    # Priority 4-6: pick the least recently used
    for ptype in ["ayuda_destacada", "dato_curioso", "tematico"]:
        if ptype not in recent_week:
            return ptype

    # Fallback: ayuda_destacada (always has data)
    return "ayuda_destacada"


def gather_data(post_type: str, db_path: str | None = None) -> tuple[dict | list | None, list[int] | None, dict | None]:
    """Query the database for the data needed by a post type.

    Args:
        post_type: The type of post to generate.
        db_path: Override path for tests.

    Returns:
        Tuple of (data_for_prompt, convocatoria_ids, metadata).
    """
    exclude_ids = get_used_convocatoria_ids(db_path)

    if post_type == "ayuda_destacada":
        grant = query_ayuda_destacada(exclude_ids, db_path)
        if not grant:
            return None, None, None
        return grant, [grant["id"]], None

    if post_type == "datos_semana":
        stats = query_datos_semana(db_path)
        return stats, None, {"stats": stats}

    if post_type == "cierre_inminente":
        grants = query_cierre_inminente(days=7, db_path=db_path)
        if not grants:
            return None, None, None
        ids = [g["id"] for g in grants]
        return grants, ids, None

    if post_type == "tematico":
        data = query_tematico(exclude_ids, db_path)
        if not data:
            return None, None, None
        ids = [g["id"] for g in data["grants"]]
        return data, ids, {"theme": data["theme"]}

    if post_type == "top_organismo":
        data = query_top_organismo(db_path)
        if not data:
            return None, None, None
        ids = [g["id"] for g in data["grants"]]
        return data, ids, {"organism": data["organism"]}

    if post_type == "dato_curioso":
        data = query_dato_curioso(db_path)
        if not data:
            return None, None, None
        return data, None, {"curiosidad_type": data["curiosidad_type"]}

    raise ValueError(f"Unknown post type: {post_type}")


async def run_generation(
    post_type: str = "auto",
    db_path: str | None = None,
) -> dict:
    """Main generation entrypoint.

    Args:
        post_type: Specific type or 'auto' for auto-selection.
        db_path: Override path for tests.

    Returns:
        Summary dict with post_type, post_id, and content lengths.
    """
    if post_type == "auto":
        post_type = select_next_post_type(db_path)
        logger.info("Auto-selected post type: %s", post_type)

    if post_type not in VALID_POST_TYPES:
        raise ValueError(f"Invalid post type: {post_type}. Valid: {VALID_POST_TYPES}")

    data, conv_ids, metadata = gather_data(post_type, db_path)
    if data is None:
        logger.warning("No data available for post type '%s'", post_type)
        return {"post_type": post_type, "status": "no_data"}

    content = await generate_post_content(post_type, data)

    post_id = insert_post(
        post_type=post_type,
        content_x=content["content_x"],
        content_linkedin=content["content_linkedin"],
        convocatoria_ids=conv_ids,
        metadata=metadata,
        db_path=db_path,
    )

    logger.info("Saved post #%d (type=%s) as draft", post_id, post_type)
    return {
        "post_type": post_type,
        "post_id": post_id,
        "status": "created",
        "content_x_length": len(content["content_x"]),
        "content_linkedin_length": len(content["content_linkedin"]),
    }


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    post_type = sys.argv[1] if len(sys.argv) > 1 else "auto"

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not set")
        sys.exit(1)

    init_posts_db()
    result = asyncio.run(run_generation(post_type))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
