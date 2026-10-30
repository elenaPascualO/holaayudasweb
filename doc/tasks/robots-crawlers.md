# Frenar crawlers que no aportan visitas (`robots.txt`)

**Estado:** implementada (30-oct-2026), pendiente de desplegar y verificar. Bots de IA: **opción A, permitirlos todos**.

## Contexto

Analytics de Coolify, últimas 24 h (30-oct-2026), sobre 27.250 peticiones:

| Bot | Peticiones | Qué es | ¿Aporta visitas? |
|---|---|---|---|
| AhrefsBot | 7.570 | Herramienta SEO de pago de terceros | No |
| SemrushBot | 2.760 | Herramienta SEO de pago de terceros | No |
| PetalBot | ~1.000 | Buscador de Huawei (Petal Search) | Prácticamente no en España |
| AwarioBot | 907 | Monitorización de marca y redes | No |
| Applebot | 913 | Siri / Spotlight / Apple | Sí |
| Bingbot | 726 | Bing (también alimenta DuckDuckGo, Ecosia, Copilot) | Sí |
| Googlebot | 98 | Google | Sí, el principal |
| OAI-SearchBot / ClaudeBot / GPTBot… | pocas | Buscadores y modelos de IA | Ver "Decisión" |
| "misc crawler" | 3.680 | Sin identificar | — |

**Solo Ahrefs, Semrush, Petal y Awario suman ~12.000 peticiones al día (~45 % del tráfico)** sin aportar visitas. Consumen CPU, disco y ancho de banda. Hasta ahora además competían con los usuarios por un servidor que se bloqueaba (ver `non-blocking-routes.md`).

`robots.txt` actual (`frontend/public/robots.txt`):

```
User-agent: *
Allow: /
Disallow: /api/

Sitemap: https://www.holaayudas.com/sitemap.xml
```

## Objetivo

Que los crawlers comerciales que no traen visitas dejen de rastrear la web, sin afectar a los buscadores que sí las traen.

## Diseño

Añadir a `frontend/public/robots.txt` un bloque `Disallow: /` para cada bot que no aporta, y mantener la regla general:

```
# Herramientas SEO, monitorización y buscadores sin audiencia en España
User-agent: AhrefsBot
User-agent: SemrushBot
User-agent: PetalBot
User-agent: AwarioBot
User-agent: MJ12bot
User-agent: DotBot
User-agent: BLEXBot
User-agent: DataForSeoBot
Disallow: /

User-agent: *
Disallow: /api/
Allow: /

Sitemap: https://www.holaayudas.com/sitemap.xml
```

- **`Disallow: /api/` va antes que `Allow: /`.** El estándar (RFC 9309), Google y `urllib.robotparser` de Python 3.13 aplican la regla **más específica**, así que el archivo actual ya bloqueaba `/api/` correctamente y el orden no les afecta. *(Corrección: la primera versión de esta spec decía que Python aplicaba la primera regla; se comprobó que no.)* Se cambia el orden solo como medida defensiva para parsers antiguos o no conformes que sí aplican la primera regla que coincide.
- MJ12bot, DotBot, BLEXBot y DataForSeoBot son del mismo tipo (SEO comercial) y se añaden de forma preventiva.
- Los cuatro principales **respetan `robots.txt`** según su documentación oficial, aunque pueden tardar hasta un día en releerlo.
- **No se usa `Crawl-delay`**: Google lo ignora, y para los bots que se bloquean es más simple un `Disallow` total.
- `robots.txt` es una petición de cortesía: los bots maliciosos y los scrapers que se hacen pasar por navegadores lo ignoran. Bloquearlos por IP o *user agent* en el proxy queda fuera de alcance.

### Decisión: bots de IA → opción A (permitirlos)

| Opción | Efecto |
|---|---|
| **A. Permitirlos (recomendada)** | Buscadores de IA (ChatGPT search con OAI-SearchBot, Perplexity, Claude…) pueden **citar y enlazar** holaayudas.com al responder preguntas sobre ayudas. Es tráfico potencial con poco coste: hoy hacen muy pocas peticiones |
| B. Permitir solo los de búsqueda | Permitir `OAI-SearchBot`, `PerplexityBot`, `Claude-SearchBot`; bloquear los de entrenamiento (`GPTBot`, `ClaudeBot`, `CCBot`, `Google-Extended`) |
| C. Bloquearlos todos | Ninguna IA usa ni cita el contenido |

Los datos son públicos (BDNS), así que el contenido en sí no es lo que se protegería; el valor de la web está en la presentación y la búsqueda.

### Archivos

| Archivo | Cambio |
|---|---|
| `frontend/public/robots.txt` | Bloque de bots bloqueados (y de IA según la decisión) |

## Tests

Nuevo `backend/tests/test_robots.py`. Lee `frontend/public/robots.txt` con `urllib.robotparser` de la librería estándar, que interpreta las reglas igual que un crawler:

| Test | Comprueba |
|---|---|
| `test_search_engines_can_crawl_pages[Googlebot/Bingbot/Applebot/DuckDuckBot]` | Pueden rastrear `/`, `/ayuda/123`, `/buscar` y `/sitemap.xml` |
| `test_seo_crawlers_blocked[AhrefsBot/SemrushBot/PetalBot/AwarioBot/…]` | No pueden rastrear `/` ni `/ayuda/123` |
| `test_api_disallowed_for_everyone` | Ningún bot (incluido Googlebot) puede rastrear `/api/convocatorias` |
| `test_sitemap_declared` | Declara `https://www.holaayudas.com/sitemap.xml` |
| `test_ai_bots_allowed[GPTBot/OAI-SearchBot/ClaudeBot/Claude-SearchBot/PerplexityBot/Google-Extended/CCBot]` | Opción A: pueden rastrear `/ayuda/123` |

**Criterio de aceptación:** toda la suite en verde.

**Resultado (30-oct-2026):** con el `robots.txt` anterior fallaban los 8 tests de bloqueo y pasaba el resto (incluido el de `/api/`, ver la corrección en Diseño). Con el nuevo: 24 passed.

## Verificación en producción

1. `curl -s https://www.holaayudas.com/robots.txt` muestra el nuevo contenido.
2. Google Search Console → Configuración → robots.txt: sin errores, y Googlebot puede rastrear `/ayuda/…`.
3. Analytics de Coolify a los 2–3 días: AhrefsBot, SemrushBot, PetalBot y AwarioBot pasan de miles de peticiones a casi cero (solo leen `robots.txt`). Googlebot y Bingbot sin cambios o al alza.
