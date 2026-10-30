# Rutas que no bloquean el servidor

**Estado:** implementada (30-oct-2026), pendiente de desplegar y verificar en producción.

## Contexto

FastAPI ejecuta todas las rutas `async def` en un único hilo, el event loop. Si una de ellas llama a una función **síncrona** lenta (una consulta a SQLite, una búsqueda FAISS), **todo el servidor se para** hasta que termina: ninguna otra petición se atiende, ni siquiera `/api/health` o los archivos estáticos.

Ya lo arreglamos en los sitemaps (`doc/tasks/sitemaps-pregenerated.md`). Allí el test demostró que una consulta de 0,6 s retrasaba `/api/health` esos mismos 0,6 s. Pero el mismo patrón sigue en otras rutas:

| Ruta | Llamada síncrona en el event loop | Coste estimado |
|---|---|---|
| `GET /api/analytics/summary`, `/by-year`, `/monthly-trend`, `/by-theme`, `/by-region`, `/top-organs`, `/status` | `analytics_*()` cuando la caché (1 h) está vacía | Alto: agregaciones sobre ~659K filas. Antes de los índices de `analytics-performance.md` tardaban ~21 s; hoy menos, pero siguen recorriendo mucho |
| `GET /api/search` (`semantic_search`) | `search_fts()`, `faiss_index.search()`, `get_convocatorias_by_ids()` | Medio: FTS5 sobre 659K + hidratar hasta cientos de filas |
| `GET /api/analytics/keyword-trend` (`keyword_trend`) | `search_fts()`, `faiss_index.search()`, `aggregate_by_year_for_ids()`, `has_beneficiarios_data()`, `search_beneficiarios_trend()` | Medio-alto |
| `GET /ayuda/{codigo}` y demás páginas (`spa_fallback` → `get_index_html_with_meta`) | `get_convocatoria_detail_local()` para inyectar el HTML SEO | Bajo por petición, pero es la ruta que más piden los bots |
| `GET /api/convocatorias/{codigo}` (`grant_detail`) | `get_convocatoria_detail_local()` | Bajo |

Las rutas de convocatorias (búsqueda y últimas), beneficiarios y posts ya usan `asyncio.to_thread` mediante sus `*_async` y no se tocan. Las llamadas a la API de BDNS son asíncronas (`httpx.AsyncClient`) y tampoco bloquean.

## Objetivo

Que ninguna ruta pública ejecute trabajo de SQLite o FAISS en el event loop. Una petición lenta solo debe hacer esperar a quien la hizo, no a todos los demás.

## Diseño

Mover cada llamada síncrona a un hilo con `await asyncio.to_thread(func, *args)`, el mismo patrón que ya usan `search_convocatorias_local_async` y compañía. **No cambia ninguna respuesta**: mismas funciones, mismos argumentos, misma caché.

| Archivo | Cambio |
|---|---|
| `backend/routes/analytics.py` | Las 7 rutas: `data = await asyncio.to_thread(analytics_x, ...)` |
| `backend/services/semantic_search.py` | En `semantic_search` y `keyword_trend`: `search_fts`, `faiss_index.search`, `get_convocatorias_by_ids`, `aggregate_by_year_for_ids`, `has_beneficiarios_data` y `search_beneficiarios_trend` vía `asyncio.to_thread` |
| `backend/main.py` | Nueva `render_page_with_meta(filename)` (módulo, siempre definida) que llama a `get_index_html_with_meta` vía `asyncio.to_thread`; `spa_fallback` la usa. *(Cambio respecto a la propuesta: `spa_fallback` solo se registra si existe `frontend/dist`, que no existe en los tests, así que la lógica se extrajo para poder probarla.)* |
| `backend/routes/convocatorias.py` | `grant_detail`: `await asyncio.to_thread(get_convocatoria_detail_local, bdns_code)` |

### Consideraciones

- **Pool de hilos.** `asyncio.to_thread` usa el executor por defecto: `min(32, nº CPUs + 4)` hilos, es decir, 8 en el servidor de 4 vCPU. Si se juntan más de 8 consultas lentas, las siguientes esperan su turno, pero **solo ellas**: el resto de rutas sigue respondiendo. Con el tráfico actual es más que suficiente.
- **SQLite y concurrencia.** Cada función abre su propia conexión. En modo WAL, varias lecturas en paralelo son seguras.
- **FAISS.** `faiss_index.search` ya toma `_lock`, así que es seguro desde varios hilos.
- **Caché.** `TTLCache` se lee y escribe desde el event loop, como hasta ahora. Solo se mueve a un hilo la función que calcula el dato.

### Fuera de alcance

- Hacer más rápidas las consultas en sí (índices, cachés). Esta spec solo evita que bloqueen al resto.
- `feedback` escribe una línea en un archivo `.jsonl` (microsegundos) y se deja como está.
- Ampliar el pool de hilos.

## Tests

Nuevo `backend/tests/test_non_blocking.py`. Para cada ruta se sustituye la función síncrona por otra que duerme 0,6 s, se lanza la petición y, 0,1 s después, una a `/api/health`. Con el tiempo medido **desde el inicio común**, `/api/health` debe terminar antes de 0,4 s. Si la ruta bloquea, terminaría hacia los 0,6 s. Es el mismo test que se validó en los sitemaps, que fallaba con el código bloqueante y pasaba con el arreglo.

| Test (parametrizado) | Ruta | Función ralentizada |
|---|---|---|
| `test_analytics_does_not_block[summary]` | `/api/analytics/summary` | `analytics_summary` |
| `…[by-year]` | `/api/analytics/by-year` | `analytics_by_year` |
| `…[monthly-trend]` | `/api/analytics/monthly-trend` | `analytics_monthly_trend` |
| `…[by-theme]` | `/api/analytics/by-theme` | `analytics_by_theme` |
| `…[by-region]` | `/api/analytics/by-region` | `analytics_by_region` |
| `…[top-organs]` | `/api/analytics/top-organs` | `analytics_top_organs` |
| `…[status]` | `/api/analytics/status` | `analytics_status` |
| `test_semantic_search_does_not_block` | `/api/search?q=…` | `search_fts` |
| `test_keyword_trend_does_not_block` | `/api/analytics/keyword-trend?q=…` | `search_fts` |
| `test_grant_detail_does_not_block` | `/api/convocatorias/{codigo}` | `get_convocatoria_detail_local` |
| `test_grant_page_does_not_block` | `render_page_with_meta("ayuda/123")` (lo que usa `/ayuda/{codigo}`) | `get_index_html_with_meta` |
| `test_grant_page_returns_none_without_meta` *(añadido)* | Sin configuración SEO devuelve `None` (y `spa_fallback` sirve `index.html`) | — |

Como validación del propio test, antes de implementar **todos deben fallar** (con `/api/health` terminando hacia los 0,6 s).

**Resultado (30-oct-2026):** antes de implementar, los 12 fallaban: los 11 de rutas con `/api/health finished at 0.61s — blocked behind the slow call` y los 2 de página porque `render_page_with_meta` aún no existía. Después de implementar: 12 passed; suite de backend 375 passed.

Los tests existentes de analytics, búsqueda semántica, keyword trend, detalle y SEO deben seguir pasando sin cambios. Los que sustituyen estas funciones con `patch` siguen funcionando, porque `to_thread` llama al mismo objeto.

**Criterio de aceptación:** toda la suite en verde (`uv run pytest` y `cd frontend && bun run test:run`).

## Verificación en producción

1. Tras el deploy, abrir `/estadisticas` justo después de un reinicio (caché vacía) y, mientras carga, navegar por otra pestaña: el resto de la web debe responder al instante.
2. Analytics de Coolify durante 2–3 días: el P95 de rutas baratas (`/robots.txt`, `/assets/*`, `/api/health`) debe quedarse en milisegundos aunque haya picos de crawlers.
3. Desde la terminal del contenedor, con la caché vacía tras un redeploy:
   ```sh
   (curl -s -o /dev/null http://localhost:8000/api/analytics/summary &) ; sleep 0.2; curl -s -o /dev/null -w "health: %{time_total}s\n" http://localhost:8000/api/health
   ```
   → `health` en milisegundos.
