# Tareas pendientes

## Despliegue Fase 3: Replica + Semantica + Analytics

Pasos para activar la Fase 3 en produccion (Railway):

- [ ] Ejecutar sync inicial via endpoint (no requiere esperar, corre en background):
  ```bash
  curl -X POST "https://holaayudas.com/api/admin/sync/convocatorias?mode=full-list" \
    -H "Authorization: Bearer $ADMIN_SECRET"
  ```
- [ ] Monitorizar progreso del sync:
  ```bash
  curl "https://holaayudas.com/api/admin/sync/convocatorias/status" \
    -H "Authorization: Bearer $ADMIN_SECRET"
  ```
- [ ] Configurar `OPENAI_API_KEY` en Railway (env var)
- [ ] Activar cron jobs en Railway:
  - `POST /api/admin/sync/convocatorias?mode=daily` — diario a las 07:00 UTC
  - `POST /api/admin/sync/convocatorias?mode=backfill-detail` — diario hasta completar
  - `POST /api/admin/sync/convocatorias?mode=backfill-embeddings` — diario hasta completar
- [ ] Tras ~2 semanas de backfill, la busqueda semantica cubrira todos los datos historicos

## Completadas

### Fix drill-down desde graficas de analytics — COMPLETADA

Los clicks en las graficas de estadísticas generaban URLs incorrectas para la pagina de busqueda:

1. **Region**: BDNS solo devuelve `descripcion` en regiones (sin ID numerico ni `codigo`). El click caia en busqueda semantica `q=ES613 - Córdoba` → sin resultados.
2. **Tematica**: `finalidad_id` siempre NULL (BDNS no lo devuelve en el detalle). El click caia en busqueda semantica `q=Agricultura...` → max 20 resultados.
3. **Estado**: El chart navegaba con `abierto=true/false` pero la busqueda no-semantica usa `estado`.

**Solucion:** Nuevos filtros `descripcionFinalidad` y `regionDesc` en el endpoint `/api/convocatorias` que hacen match exacto por texto (valido porque el valor viene del propio `GROUP BY` de analytics). Status chart ahora usa `estado=abiertas/cerradas`. Se omite el filtro de fecha por defecto al venir de analytics.

Archivos modificados:
- `convocatorias_db.py`: Nuevos filtros `descripcion_finalidad` y `region_desc` en `search_convocatorias_local()`
- `convocatorias.py`: Nuevos query params `descripcionFinalidad` y `regionDesc`
- `analytics.js`: Charts navegan con params correctos (region, tema, estado)
- `search.js`: Pasa nuevos params al backend, omite filtro de fecha por defecto para drill-down

### Migracion endpoints BDNS proxy a SQLite local — COMPLETADA

Endpoints migrados a local-first (SQLite como fuente primaria, BDNS como fallback):

- `GET /api/convocatorias` — busqueda con todos los filtros (texto FTS5, fechas, tipo admin, regiones, instrumentos, tiposBeneficiario, finalidad, estado, orden)
- `GET /api/convocatorias/ultimas` — ultimas convocatorias publicadas
- `GET /api/beneficiarios-top?anio=X` — top beneficiarios por año
- `GET /api/beneficiarios-top?nifCif=X` — beneficiario por NIF/CIF
- `GET /api/beneficiarios-top/anios` — años disponibles

Bug corregido: `_row_to_search_result()` no exponía `nivel1`/`nivel2`/`nivel3` como campos top-level, causando que GrantCard mostrara el convocante vacío en resultados de SQLite local.

Archivos modificados:
- `convocatorias_db.py`: Fix `_row_to_search_result()` + `has_convocatorias_data()` + `search_convocatorias_local()` + `get_latest_convocatorias_local()` + async wrappers
- `beneficiarios_db.py`: `get_top_beneficiarios_by_year()` + `get_beneficiario_by_nif()` + `get_available_years()` + async wrappers
- `convocatorias.py`: `search_grants()` y `latest_grants()` usan local-first con fallback
- `beneficiarios.py`: `get_top_beneficiaries()` (path 3) y `get_years()` usan local-first con fallback
- Tests actualizados para mockear `has_data`/`has_convocatorias_data` en tests de fallback BDNS

### Sync en background con endpoint de estado — COMPLETADA

El endpoint `POST /api/admin/sync/convocatorias` ahora lanza el sync como tarea async en background y retorna inmediatamente `{"status": "started"}`. Esto evita que Railway corte la peticion HTTP por timeout (~5 min).

- `sync_convocatorias.py`: `progress_callback` opcional en todas las funciones de sync
- `admin.py`: `asyncio.create_task()` + estado global `_sync_state` (idle/running/completed/failed/cancelled)
- `admin.py`: Nuevo `GET /api/admin/sync/convocatorias/status` — devuelve estado + progreso
- `main.py`: `cancel_sync_task()` en lifespan shutdown
- `test_admin_sync.py`: 10 tests (started, rejected, idle/running/completed, auth, completion, failure)

### Fase 3: Replica Local + Busqueda Semantica + Analytics — COMPLETADA

Implementacion de las fases 1-3 del KILLER_PLAN.md:

#### 1. Replica local de convocatorias en SQLite
- `convocatorias_db.py`: Schema, FTS5, upsert, detail update, analytics queries
- `sync_convocatorias.py`: 4 modos (daily, full-list, backfill-detail, backfill-embeddings)
- `admin.py`: Endpoint `POST /api/admin/sync/convocatorias?mode=daily` (background)
- `convocatorias.py`: Detalle servido desde local → fallback BDNS proxy
- `config.py`: `CONVOCATORIAS_DB_PATH`, `OPENAI_API_KEY`
- `main.py`: `init_convocatorias_db()` en lifespan startup

#### 2. Busqueda semantica
- `embeddings.py`: OpenAI `text-embedding-3-small`, blob encoding/decoding
- `semantic_search.py`: Busqueda hibrida FTS5 pre-filtro + coseno re-rank con numpy
- `semantic.py` (route): `GET /api/search?q=...&topK=&yearFrom=&yearTo=&abierto=`
- `search.js`: Pagina `/buscar` usa busqueda semantica cuando `q` esta presente
- `FilterPanel.js`: `createSemanticFilterPanel()` con filtros simplificados (año, estado)

#### 3. Dashboard de analytics
- `analytics.py` (route): 7 endpoints con cache 1h
- `convocatorias_db.py`: 6 funciones analytics (summary, by_year, monthly_trend, by_theme, by_region, top_organs, status)
- `analytics.js`: Pagina `/datos` con Chart.js v4 (CDN)
- `api.js`: 7 funciones fetch para analytics
- `Header.js`: Enlace "Datos" en navegacion
- `main.js`: Router + Chart.js init tras render
- `index.html`: Script CDN de Chart.js v4

#### 4. Tests
- `test_convocatorias_db.py`: Tests de schema, upsert, detail, FTS, analytics
- `test_semantic_search.py`: Tests de busqueda hibrida
- `test_analytics.py`: Tests de endpoints analytics

#### 5. Dependencias
- `openai>=1.0.0` y `numpy>=1.26.0` añadidos a pyproject.toml

### Sprints anteriores

#### Bug: Beneficiarios duplicados en Transparencia con "Todos" los años — RESUELTO

**Solución:** Agregación por `nif_cif` con `GROUP BY` + `SUM(ayuda_e_total)` en SQLite cuando `anio` es None.

#### Mejora: Documentos abren en visor PDF del navegador — COMPLETADO

**Solución:** Nuevo endpoint proxy `GET /api/documentos/{doc_id}` que cambia `Content-Disposition` de `attachment` a `inline`.

#### Mejora: Visibilidad del enlace Transparencia en header — COMPLETADO

**Solución:** Enlace convertido en pill/badge con estilos destacados.
