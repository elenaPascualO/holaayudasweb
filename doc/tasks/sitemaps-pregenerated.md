# Sitemaps pregenerados en disco y sin bloquear el servidor

**Estado:** implementada y **verificada en producción** (30-oct-2026, deploy `43a151f`). Queda el seguimiento de 2–3 días (analytics y Search Console).

## Contexto

Analytics de Coolify, últimas 24 h (30-oct-2026):

| Ruta | Error | P95 |
|---|---|---|
| `/sitemap.xml` | **71,4 %** | **49,7 s** |
| `/sitemap-grants-open-3.xml` | 20 % | 25 s |
| `/sitemap-grants-open-1.xml` | 0 % | 8,4 s |
| `/robots.txt` (archivo estático) | 4,8 % | 485 ms |

Además hay **114 respuestas 499**: el cliente cerró la conexión antes de recibir respuesta. Los crawlers, Google incluido, se cansan de esperar. Si Google no puede leer el sitemap, tarda más en descubrir e indexar las ayudas. Ahora mismo solo llegan **7 visitas al día desde google.com**.

### Causas (análisis del código)

1. **Los sitemaps bloquean toda la aplicación.** Las rutas de `backend/routes/seo.py` son `async def`, pero llaman a funciones síncronas de SQLite (`get_sitemap_*`) **directamente en el event loop**. Mientras se genera un sitemap, el servidor no atiende ninguna otra petición. Eso explica que hasta `/robots.txt`, un archivo estático, tenga un P95 de 485 ms y errores 499.
2. **Las consultas son caras.**
   - `get_sitemap_closed_by_year()` agrupa ~600K filas por `substr(fecha_recepcion, 1, 4)` y calcula `MAX(updated_at)`. `updated_at` no está en ningún índice, así que hay que leer cada fila de una tabla de varios GB.
   - `get_sitemap_*_entries()` seleccionan `numero_convocatoria` y `updated_at`, que no están en `idx_conv_sitemap`, y ordenan por `fecha_recepcion` después de filtrar por rango de `fecha_fin_solicitud`. Eso obliga a leer la tabla y a ordenar en memoria hasta 50K filas.
3. **La caché es en memoria y se pierde a menudo.** `_sitemap_cache` (`TTLCache`) se vacía en cada reinicio o redeploy. El índice caduca cada hora, y `invalidate_sitemap_cache()` borra el índice y los sitemaps abiertos tras cada sync. Muchas peticiones de crawlers encuentran la caché fría y les toca esperar la generación completa.
4. La carga del servidor (por ejemplo, la construcción de FAISS) lo empeora, pero no es la causa principal.

## Objetivo

1. Servir cualquier sitemap en **menos de 100 ms**, también justo después de un reinicio.
2. Que generar sitemaps **no bloquee nunca** el resto de peticiones.
3. Mantener los sitemaps al día: regenerarlos tras cada sync `daily` y al arrancar si faltan o tienen más de 24 h.
4. Que las URLs y el contenido XML no cambien para Google: mismas rutas, mismo formato, mismos `changefreq` y `priority`.

## Diseño

### Generación en segundo plano y guardado en disco

Nuevo módulo `backend/services/sitemaps.py`:

- `generate_all(db_path=None, out_dir=None) -> dict`
  - Genera **todos** los sitemaps (estático, abiertos paginados y cerrados por año y página) reutilizando la lógica actual de construcción del XML y las consultas existentes.
  - Escribe cada archivo comprimido en `SITEMAPS_DIR` (por defecto `/app/data/sitemaps/`, en el volumen persistente), por ejemplo `sitemap-grants-closed-2025.xml.gz`.
  - **Escritura atómica** de cada archivo (`.tmp` y `os.replace`). **El índice `sitemap.xml.gz` se escribe el último**, así nunca apunta a archivos que todavía no existen.
  - Después de escribir el índice, **borra los archivos que ya no aparecen en él** (por ejemplo, si una página de abiertos desaparece).
  - Escribe `sitemaps.meta.json` con `generated_at` y la lista de archivos.
  - Devuelve `{"files": N, "urls": M, "elapsed_seconds": s}`.
  - Un bloqueo (`threading.Lock`) evita dos generaciones simultáneas: si ya hay una en curso, devuelve `skipped`.
- `is_generating()`, `get_status()` (archivos, `generated_at`, si está generando).
- `needs_regeneration(max_age_hours=24) -> bool`: falta el índice, falta el meta o tiene más de 24 h.

**Cuándo se genera:**

| Momento | Cómo |
|---|---|
| Arranque | En segundo plano (`asyncio.to_thread`), solo si `needs_regeneration()` |
| Tras un sync `daily` completado | En segundo plano, sustituye a `invalidate_sitemap_cache()` |
| A mano | `POST /api/admin/sitemaps/regenerate` (admin + rate limit) → `started` / `skipped` |

Si la generación falla, se registra en el log y se envía el email de alerta existente, y **se siguen sirviendo los archivos anteriores**.

### Servir los sitemaps

Las rutas actuales (`/sitemap.xml`, `/sitemap-static.xml`, `/sitemap-grants-open-{page}.xml`, `/sitemap-grants-closed-{segment}.xml`) pasan a:

1. Validar el nombre como ahora (página ≥ 1, regex del segmento) y construir el nombre de archivo. No se aceptan rutas arbitrarias, así que no hay *path traversal*.
2. Si el archivo existe, leerlo con `asyncio.to_thread` y servirlo:
   - con `Content-Encoding: gzip` si el cliente lo acepta (caso normal: Google, Bing),
   - descomprimido si no lo acepta.
   - Se mantienen las cabeceras `Cache-Control` actuales.
3. Si no existe (primer arranque, antes de terminar la primera generación): **fallback a la generación bajo demanda actual, pero en un hilo** (`asyncio.to_thread`) para no bloquear, conservando la `TTLCache` en memoria solo para este caso.

`invalidate_sitemap_cache()` se mantiene en el flujo de sync, pero ahora solo limpia la caché en memoria del fallback, para que no sirva datos viejos mientras no existan los archivos. *(Cambio respecto a la propuesta, que la eliminaba.)*

### Configuración

| Variable | Default |
|---|---|
| `SITEMAPS_DIR` | `sitemaps/` junto a `CONVOCATORIAS_DB_PATH` (es decir, `/app/data/sitemaps`) |

### Archivos afectados

| Archivo | Cambio |
|---|---|
| `backend/config.py` | `SITEMAPS_DIR` |
| `backend/services/sitemaps.py` (nuevo) | Generación, escritura atómica, estado, bloqueo |
| `backend/routes/seo.py` | Servir desde disco, fallback en hilo; la construcción del XML se mueve al servicio |
| `backend/routes/admin.py` | Regenerar tras `daily`; endpoint `POST /api/admin/sitemaps/regenerate`; `GET /api/admin/sitemaps/status` |
| `backend/main.py` | Generación en segundo plano al arrancar si hace falta |
| `data/.gitignore` | Ignorar `sitemaps/` |
| `doc/OPERACIONES.md` | Endpoints, logs, verificación |

### Fuera de alcance

- **Índice que cubra todas las columnas de la consulta** (`detail_fetched, fecha_fin_solicitud, fecha_recepcion, numero_convocatoria, updated_at`) para acelerar la generación. Crearlo sobre una tabla de varios GB lleva minutos y bloquea escrituras, y con la generación en segundo plano deja de ser crítico. Se decidirá con los tiempos de generación medidos (se registran en el log).
- **Otras rutas que también llaman a SQLite de forma síncrona** desde `async def` (`convocatorias`, `analytics`, `beneficiarios`, `concesiones`…). Es el mismo problema de bloqueo del event loop y merece su propia spec.
- Limitar crawlers (Ahrefs, Semrush…) en `robots.txt`.

## Tests

`backend/tests/test_sitemaps.py` (nuevo). Usan una BD temporal con convocatorias abiertas y cerradas de varios años, y `_GRANTS_PER_SITEMAP` reducido para forzar la paginación:

| Test | Comprueba |
|---|---|
| `test_generate_writes_all_files` | Genera índice, estático, abiertos y cerrados por año como `.xml.gz` en `out_dir` |
| `test_index_lists_exactly_generated_files` | El índice referencia todos los archivos generados y ninguno más |
| `test_open_sitemap_contains_open_grants_only` | Las URLs `/ayuda/{numero}` de abiertas están en `open-N` y no en cerradas |
| `test_closed_sitemaps_split_by_year_and_page` | Un año con más entradas que el tamaño de página genera `YYYY` y `YYYY-2` |
| `test_xml_content_unchanged` | Mismo XML (loc, lastmod, changefreq, priority) que la generación bajo demanda actual |
| `test_removes_stale_files` | Si desaparece una página, su archivo se borra tras regenerar |
| `test_no_tmp_files_left` | No quedan `.tmp` tras generar |
| `test_concurrent_generation_skipped` | Con el bloqueo ocupado, `generate_all` devuelve `skipped` |
| `test_builders_match_generated_files` | Los builders del fallback producen exactamente el mismo XML que los archivos *(añadido)* |
| `test_needs_regeneration` | Verdadero sin archivos o con meta de más de 24 h; falso con una generación reciente |
| `test_needs_regeneration_when_index_missing` | Verdadero si falta el índice aunque exista el meta *(añadido)* |
| `test_get_status` | Estado antes y después de generar *(añadido)* |
| `test_read_sitemap` / `test_read_sitemap_rejects_unknown_names` | Lectura del gzip; rechaza nombres no válidos (`../`, meta) *(añadido)* |
| `test_generation_is_reasonably_fast` | Con una BD pequeña, la generación tarda menos de 2 s *(añadido)* |

`backend/tests/test_seo.py` (rutas):

| Test | Comprueba |
|---|---|
| `test_sitemap_served_from_disk_gzip` | Con archivo generado: 200, `Content-Encoding: gzip`, contenido correcto |
| `test_sitemap_served_uncompressed_without_gzip` | Sin `Accept-Encoding: gzip`: XML plano |
| `test_sitemap_fallback_when_not_generated` | Sin archivos: se genera bajo demanda y responde 200 con el XML correcto |
| `test_sitemap_invalid_segment_returns_empty_urlset` | Segmentos inválidos y página 0 siguen devolviendo un urlset vacío |
| `test_sitemap_fallback_does_not_block_event_loop` | Con la consulta del fallback ralentizada artificialmente, una petición concurrente a `/api/health` responde sin esperar |

`backend/tests/test_admin_sync.py`:

| Test | Comprueba |
|---|---|
| `test_sitemaps_regenerate_requires_token` | 401 sin token |
| `test_sitemaps_regenerate_starts_in_background` | `started` y llama a `generate_all` |
| `test_sitemaps_regenerate_skipped_while_generating` | `skipped` con la generación en curso |
| `test_sitemaps_status_endpoint` | `GET /sitemaps/status` devuelve `generating` y `generated_at` *(añadido)* |
| `test_daily_sync_triggers_sitemap_regeneration` | Al completar un `daily` se lanza la regeneración (y no con otros modos) |

**Criterio de aceptación:** toda la suite en verde (`uv run pytest` y `cd frontend && bun run test:run`).

**Resultado (30-oct-2026):** backend 363 passed; frontend 91 passed. Se comprobó que `test_sitemap_fallback_does_not_block_event_loop` **falla con el código bloqueante anterior** (`/api/health` termina a los 0,61 s) y pasa con el nuevo; la primera versión del test no lo detectaba y se corrigió.

## Verificación en producción

1. **Primer arranque tras el deploy.** En los logs: `Generating sitemaps…` → `Sitemaps generated: N files, M URLs in S s`. Después:
   ```sh
   ls -la /app/data/sitemaps/
   curl -s -H "Authorization: Bearer $ADMIN_SECRET" http://localhost:8000/api/admin/sitemaps/status
   ```
2. **Tiempo de respuesta**, desde fuera:
   ```sh
   curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" -H "Accept-Encoding: gzip" https://www.holaayudas.com/sitemap.xml
   curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" -H "Accept-Encoding: gzip" https://www.holaayudas.com/sitemap-grants-open-1.xml
   ```
   → `200` y menos de 1 s (la mayor parte es red).
3. **Contenido válido:** `curl -s --compressed https://www.holaayudas.com/sitemap.xml | head -20`.
4. **Tras un reinicio:** el log **no** debe mostrar una nueva generación si la anterior tiene menos de 24 h, y los sitemaps deben seguir respondiendo al instante.
5. **En 2–3 días:**
   - Analytics de Coolify: P95 de `/sitemap*.xml` en milisegundos, error ~0 % y los 499 prácticamente desaparecidos. El P95 de `/robots.txt` también debería bajar.
   - Google Search Console → Sitemaps: estado **"Correcto"** y número de URLs descubiertas al alza.

## Resultado de la verificación (30-oct-2026)

- Log del arranque: `Sitemaps generated: 21 files, 658932 URLs in 7.2s` (tras crear los índices de `sitemap-covering-index.md`).
- Desde fuera, con `Accept-Encoding: gzip` (incluye latencia de red): `/sitemap.xml` **0,28 s** (antes P95 49,7 s y 71 % de errores), `/sitemap-grants-open-1.xml` 0,35 s (antes 8,4 s), `/sitemap-grants-closed-2025.xml` 0,36 s. Todas 200 con `Content-Encoding: gzip` y los `Cache-Control` esperados.
- El índice lista 20 sitemaps: estático, `open-1`…`open-6` y cerrados de 2014 a 2026.
- Observación: 6 páginas de abiertas implican ~250–300K ayudas "abiertas" (sin `fecha_fin_solicitud` o con fecha futura). El criterio es el mismo de antes; revisar si muchas sin fecha de fin están realmente cerradas (candidata a spec).
