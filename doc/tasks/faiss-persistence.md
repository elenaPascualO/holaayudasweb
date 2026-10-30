# Índice FAISS persistido en disco con actualización incremental

**Estado:** implementada (commit `f4d1f16`) y **verificada en producción** (30-oct-2026, pasos 1 y 2; el 3 queda para el próximo `daily`). Esta spec se escribió después de implementar; a partir de ahora las specs van antes del código (ver `AGENTS.md`).

## Contexto

El índice FAISS (`OPQ64,IVF1024,PQ64`, ~659K vectores) solo vivía en memoria:

- Se **construía desde cero en cada arranque**: más de 12 minutos y **~5 GB de RSS** (medido en producción, oct 2026) en un servidor de **8 GB**. Durante ese tiempo la búsqueda semántica no funcionaba (solo FTS).
- Tras cada sync `daily` o `backfill-embeddings` se **volvía a construir entero**, aunque solo hubiera unos cientos de vectores nuevos.
- Nada impedía que hubiera **dos construcciones a la vez**.

**Incidente (30-oct-2026):** tras un redeploy (cambio de `OPENAI_API_KEY`) se lanzó un `backfill-embeddings` de 28K vectores. Terminó en ~100 s, mientras la construcción del arranque seguía en marcha, y lanzó una segunda. Las dos juntas (~10 GB) no cabían, el kernel mató el contenedor y Coolify lo reinició. Resultado: `ready:false` durante más de 12 minutos extra y el estado de los syncs perdido.

## Objetivo

1. Arranque en segundos, sin construir el índice, cuando ya existe uno guardado.
2. Tras un sync, añadir solo los vectores nuevos, sin reentrenar.
3. Imposibilidad de que haya dos construcciones a la vez.
4. Poder reentrenar a mano de forma ocasional.
5. SQLite sigue siendo la fuente de verdad; el archivo es una caché que se puede borrar.

## Diseño

### Por qué no hace falta reconstruir

`IVF + PQ` tiene dos fases: **entrenamiento** (aprende centroides y compresión con una muestra de 50K; es lo caro) e **inserción** (comprime cada vector y lo coloca en su lista; milisegundos para cientos de vectores). Un índice entrenado admite inserciones indefinidamente. Reentrenar solo mejora la calidad si la distribución de los datos cambia mucho, así que basta con hacerlo cada pocos meses.

### Flujos

```
ARRANQUE  load_or_build()
  ¿existe faiss.index + meta compatible y legible?
    sí → read_index (segundos, ~100 MB) → swap → añadir embeddings de SQLite que falten → guardar si añadió
    no → construcción completa → añadir los que falten → swap → guardar

TRAS SYNC daily / backfill-embeddings  sync_from_db()
  → añadir embeddings de SQLite que no estén en el índice (sin reentrenar) → guardar

REENTRENAMIENTO  POST /api/admin/faiss/rebuild → load_index_from_db()
  → construcción completa en paralelo al índice vivo → añadir los que falten → swap → guardar
```

"Añadir los que falten" = `setdiff1d(ids en conv_embeddings, ids en el índice)`. Solo lee la columna de IDs (barato); los BLOBs se leen por lotes solo para los que faltan. Esto cubre cualquier hueco: un sync que se ejecutó con la app parada, un contenedor que murió entre guardar en SQLite y guardar el índice, o embeddings creados mientras se construía.

### Persistencia

- Archivo: `FAISS_INDEX_PATH` (por defecto `faiss.index` junto a `CONVOCATORIAS_DB_PATH`, es decir `/app/data/faiss.index`, en el volumen persistente) + `faiss.index.meta.json`.
- Metadatos: `format_version`, `embedding_model`, `dims`, `total_vectors`, `built_at`, `saved_at`.
- Escritura **atómica**: se escribe en `.tmp` y se hace `os.replace`, así un corte a mitad nunca deja un archivo corrupto en su sitio.
- Al cargar se reconstruye si: falta el archivo o el meta, cambia `format_version` / `embedding_model` / `dims`, el archivo no se puede leer, o no es un `IndexIDMap2` con las dimensiones esperadas.
- Tamaño esperado en disco: ~50–100 MB.

### Concurrencia

- `_write_lock`: serializa **todas** las escrituras (construcción, inserción incremental, guardado). `sync_from_db` espera si hay una construcción en curso y después añade lo que esa construcción no incluyó.
- `_lock`: protege el índice vivo frente a búsquedas concurrentes. `search()` lo toma, y las inserciones en el índice vivo lo toman por bloques de 5.000 vectores para no bloquear las búsquedas mucho tiempo.
- `POST /faiss/rebuild` devuelve `skipped` si `_write_lock` está ocupado.

### API

| Cambio | Detalle |
|---|---|
| `GET /api/admin/faiss/status` | Añade `building`, `built_at`, `on_disk`, `index_path` (mantiene `ready`, `total_vectors`, `index_type`) |
| `POST /api/admin/faiss/rebuild` (nuevo) | Admin + rate limit. Lanza el reentrenamiento en segundo plano. `started` / `skipped`. Si falla, email de alerta |

### Archivos

| Archivo | Cambio |
|---|---|
| `backend/config.py` | `FAISS_INDEX_PATH` |
| `backend/services/faiss_index.py` | `load_or_build`, `sync_from_db`, `is_building`, persistencia, bloqueos; `load_index_from_db` pasa a ser "reentrenar y guardar" |
| `backend/services/convocatorias_db.py` | `get_embedding_ids`, `get_embeddings_by_ids` |
| `backend/main.py` | Arranque con `load_or_build` |
| `backend/routes/admin.py` | Tras sync, `sync_from_db` en vez de reconstruir; endpoint `/faiss/rebuild` |
| `data/.gitignore` | Ignorar `faiss.index*` |
| `doc/OPERACIONES.md` | Runbook actualizado |

### Fuera de alcance

- **Reducir los ~5 GB de la construcción completa.** Sospecha principal: `sample_embeddings` usa `ORDER BY RANDOM() LIMIT 50000`, que recorre los ~4 GB de BLOBs. Ahora solo afecta al primer arranque y a los reentrenamientos manuales. Pendiente de una spec propia.
- Límite de memoria del contenedor en Coolify.
- Borrado o actualización de embeddings existentes. Hoy no ocurre: solo se generan para convocatorias sin embedding.

## Tests

En `backend/tests/test_faiss_index.py`:

| Test | Comprueba |
|---|---|
| `TestPersistence::test_rebuild_saves_index_and_metadata` | La construcción guarda índice + meta con modelo, dims, total y `built_at` |
| `TestPersistence::test_load_or_build_builds_when_no_file` | Sin archivo → construye y guarda |
| `TestPersistence::test_load_or_build_reads_from_disk_without_rebuilding` | Con archivo → carga sin llamar a la construcción; búsqueda correcta; conserva `built_at` |
| `TestPersistence::test_load_or_build_adds_embeddings_stored_after_save` | Embeddings añadidos con la app parada se incorporan al arrancar y se guardan |
| `TestPersistence::test_incompatible_metadata_triggers_rebuild` | Otro `embedding_model` → reconstruye |
| `TestPersistence::test_corrupt_file_triggers_rebuild` | Archivo corrupto → reconstruye |
| `TestPersistence::test_empty_db_does_not_save` | Sin embeddings → ni índice ni archivo |
| `TestIncrementalSync::test_adds_new_embeddings_without_rebuild` | `sync_from_db` añade sin reentrenar y el vector nuevo es buscable |
| `TestIncrementalSync::test_saves_after_adding` | Lo añadido persiste en disco |
| `TestIncrementalSync::test_noop_when_up_to_date` | Nada que añadir → 0 |
| `TestIncrementalSync::test_skips_when_index_not_loaded` | Sin índice cargado → no hace nada |
| `TestWriteLock::*` | `is_building()` y `stats["building"]` reflejan el bloqueo |
| `TestTrainedIndexPersistence::test_round_trip_and_incremental_add` | Índice IVF entrenado: guardar, cargar (con `nprobe`), añadir y encontrar el vector nuevo |

En `backend/tests/test_admin_sync.py`:

| Test | Comprueba |
|---|---|
| `test_faiss_rebuild_requires_token` | 401 sin token válido |
| `test_faiss_rebuild_starts_in_background` | `started` y lanza la reconstrucción |
| `test_faiss_rebuild_skipped_while_building` | `skipped` si el bloqueo está ocupado, sin lanzar nada |

Los tests existentes de `load_index_from_db`, búsqueda, `add_vectors` y entrenamiento en 2 pasadas siguen pasando sin cambios.

**Criterio de aceptación:** toda la suite en verde. Resultado (30-oct-2026): backend `uv run pytest` → 336 passed; frontend `bun run test:run` → 91 passed.

## Verificación en producción

**1. Primer despliegue** (todavía no existe el archivo, así que se hace una última construcción completa):
- Logs: `No saved FAISS index at /app/data/faiss.index` → `Building FAISS index…` → `Pass 1/2` / `Pass 2/2` → `FAISS index ready: 658926 vectors indexed` → `FAISS index saved to /app/data/faiss.index`.
- Durante la construcción, `faiss/status` → `"building": true, "ready": false`.
- Al acabar:
  ```sh
  curl -s -H "Authorization: Bearer $ADMIN_SECRET" http://localhost:8000/api/admin/faiss/status
  ls -la /app/data/faiss.index*
  ```
  → `"ready": true, "total_vectors": 658926, "on_disk": true, "building": false`, y el archivo pesa unas decenas de MB.

> **Resultado (30-oct-2026):** la construcción completa tardó **30 min** (11:59 → 12:29), no los ~12 min estimados: `Pass 1` 35 s, **entrenamiento 25 min**, `Pass 2` 4 min. Pico de RSS ~3,8–4,9 GB. `faiss/status` → `ready: true, total_vectors: 658926, on_disk: true`; `faiss.index` = 70 MB, `faiss.index.meta.json` = 201 B. Un benchmark local con datos aleatorios (50K × 1536, 4 hilos) reparte el entrenamiento en **OPQ 863 s (98,5 %)** + IVF/PQ 13 s: la rotación OPQ es el cuello de botella (candidata a spec propia).

**2. Segundo arranque: la prueba clave.** Reinicia o vuelve a desplegar:
- Logs: `FAISS index loaded from disk: 658926 vectors` **en segundos**, sin `Building FAISS index`.
- `faiss/status` → `ready: true` casi de inmediato, y `built_at` igual que antes.
- Memoria del proceso (comando de `/proc` del runbook): cientos de MB, no ~5 GB.

> **Resultado (30-oct-2026, deploy `43a151f`):** `Application startup complete` a las 12:56:22,119 y `FAISS index loaded from disk: 658926 vectors (built 2026-10-30T12:29:08)` a las 12:56:22,238 → **~0,1 s**, sin `Building`. ✅

**3. Actualización incremental:**
```sh
curl -s -X POST -H "Authorization: Bearer $ADMIN_SECRET" "http://localhost:8000/api/admin/sync/convocatorias?mode=daily"
```
- Logs al terminar: `Updating FAISS index after daily sync` → `Added N new vectors to FAISS index (total: …)` + `FAISS index saved…`, o `already up to date`. **No** debe aparecer `Building FAISS index`.
- `faiss/status`: `total_vectors` = `with_embedding` de `/sync/convocatorias/stats`.

**4. Búsqueda semántica:**
```sh
curl -s "http://localhost:8000/api/search?q=ayudas%20para%20j%C3%B3venes%20que%20quieren%20montar%20un%20negocio&topK=5" | head -c 1500
```
→ resultados relevantes y ningún `Failed to embed query`.

**5. (Opcional) Bloqueo:** con `building: true`, `POST /faiss/rebuild` debe responder `skipped`.
