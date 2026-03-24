# Mejora de rendimiento: Página de Estadísticas

## Problema

Las queries de analytics hacen full table scan sobre la tabla `convocatorias` que pesa **5.6 GB**.
El 68% de ese tamaño (~3.8 GB) son embeddings BLOB de 6 KB por fila que ya no se usan en runtime
(FAISS los carga una vez al arrancar y luego busca en RAM).

**Tiempos medidos (cold start, sin cache):**

| Query | Tiempo |
|-------|--------|
| summary | 21.4s |
| by_year | 21.3s |
| by_theme | 21.0s |
| by_region | 21.6s |
| top_organs | 20.8s |
| status | 0.06s |

El frontend ejecuta las 6 en paralelo, así que el usuario espera ~21s en cold start.
Después la cache de 1h evita repetir, pero el primer acceso es inaceptable.

## Objetivo

Reducir el cold start de la página de estadísticas de ~21s a <1s.

## Plan

### Paso 1: Migrar embeddings a tabla separada `conv_embeddings`

**Qué**: Mover las columnas `embedding` y `embedding_version` de `convocatorias` a una nueva
tabla `conv_embeddings(convocatoria_id INTEGER PRIMARY KEY, embedding BLOB, version INTEGER)`.

**Por qué**: La tabla principal pasa de 5.6 GB a ~1.8 GB. Cualquier full scan (analytics, search,
latest) deja de leer 3.8 GB de blobs innecesarios.

**Archivos a modificar:**

1. **`convocatorias_db.py`**
   - `init_convocatorias_db()`: Crear tabla `conv_embeddings` en el schema.
     Añadir migración automática: si `convocatorias.embedding` existe, mover datos a la nueva tabla
     y eliminar las columnas (o dejarlas vacías y marcar como deprecated si SQLite no soporta DROP COLUMN
     en la versión disponible — SQLite >= 3.35.0 sí lo soporta).
   - `store_embeddings()`: INSERT/UPDATE en `conv_embeddings` en vez de UPDATE en `convocatorias`.
   - `get_unembedded_ids()`: LEFT JOIN con `conv_embeddings` para encontrar los que faltan.
   - `get_backfill_stats()` y `get_sync_status()`: Consultar `conv_embeddings` para conteos de embeddings.
   - `iter_all_embeddings()`: SELECT de `conv_embeddings` en vez de `convocatorias`.
   - `get_embedding_count()`: COUNT sobre `conv_embeddings`.

2. **`faiss_index.py`**
   - `load_index_from_db()`: Ya usa `iter_all_embeddings()` y `get_embedding_count()` que se
     actualizarán en el paso anterior. No requiere cambios directos.

3. **`sync_convocatorias.py`**
   - `sync_backfill_embeddings()`: Adaptar a la nueva tabla. La lógica es la misma pero
     `store_embeddings()` y `get_unembedded_ids()` apuntarán a `conv_embeddings`.

4. **`embeddings.py`** — Sin cambios (genera vectores, no toca DB).

5. **`semantic_search.py`** — Sin cambios (usa FAISS en RAM, no toca embeddings en DB).

**Migración de datos:**
- En `init_convocatorias_db()`, detectar si la columna `embedding` existe en `convocatorias`.
- Si existe y tiene datos: copiar a `conv_embeddings` en batches (para no bloquear).
- Después: `ALTER TABLE convocatorias DROP COLUMN embedding` y
  `ALTER TABLE convocatorias DROP COLUMN embedding_version`.
- Ejecutar `VACUUM` para reclamar espacio (esto puede tardar unos minutos en la primera ejecución,
  pero solo ocurre una vez).

### Paso 2: Añadir covering indexes para analytics

**Qué**: Crear índices que contengan todas las columnas que necesita cada query de analytics,
para que SQLite haga "index-only scans" sin tocar la tabla principal.

**Índices a crear** (en `init_convocatorias_db()`):

```sql
-- analytics_summary: COUNT(*), SUM(presupuesto_total), fecha_fin_solicitud
CREATE INDEX IF NOT EXISTS idx_analytics_summary
    ON convocatorias(presupuesto_total, fecha_fin_solicitud);

-- analytics_by_year: GROUP BY strftime('%Y', fecha_recepcion), SUM(presupuesto_total)
CREATE INDEX IF NOT EXISTS idx_analytics_year
    ON convocatorias(fecha_recepcion, presupuesto_total);

-- analytics_by_theme: GROUP BY descripcion_finalidad, SUM(presupuesto_total)
CREATE INDEX IF NOT EXISTS idx_analytics_theme
    ON convocatorias(descripcion_finalidad, finalidad_id, fecha_recepcion, presupuesto_total);

-- analytics_top_organs: GROUP BY nivel1, nivel2, SUM(presupuesto_total)
CREATE INDEX IF NOT EXISTS idx_analytics_organs
    ON convocatorias(nivel2, nivel1, fecha_recepcion, presupuesto_total);

-- analytics_by_region: json_each(regiones_json) — covering index
CREATE INDEX IF NOT EXISTS idx_analytics_region
    ON convocatorias(regiones_json, fecha_recepcion, presupuesto_total);
```

**Nota**: Estos índices se añaden después de la migración del Paso 1, cuando la tabla ya es
más ligera (~1.8 GB). Crearlos sobre la tabla actual de 5.6 GB sería mucho más lento.

### Paso 3 (opcional): Pre-calentar cache de analytics al arrancar

**Qué**: En el `lifespan` de FastAPI (en `main.py`), después de inicializar las DBs,
ejecutar las 6 queries de analytics en un `asyncio.create_task` en background
(igual que se hace con FAISS).

**Por qué**: Si tras los pasos 1-2 las queries bajan a <1s, este paso es menos crítico.
Pero si alguna sigue tardando más (especialmente `by_region` con `json_each`), el pre-warming
garantiza que el primer usuario vea la página al instante.

**Implementación**:
```python
# En main.py lifespan, después de init_convocatorias_db()
async def _warm_analytics_cache():
    from backend.services.convocatorias_db import (
        analytics_summary, analytics_by_year, analytics_by_theme,
        analytics_by_region, analytics_top_organs, analytics_status,
    )
    from backend.services.cache import cache
    pairs = [
        ("analytics:summary", analytics_summary),
        ("analytics:by-year", analytics_by_year),
        ("analytics:by-year", analytics_by_year),
        ...
    ]
    for key, fn in pairs:
        result = fn()
        cache.set(key, result, 3600)

asyncio.create_task(asyncio.to_thread(_warm_analytics_cache))
```

Solo se implementará si los benchmarks post Paso 1+2 lo justifican.

### Paso 4: Tests

- Actualizar `test_convocatorias_db.py`: tests de `store_embeddings`, `get_unembedded_ids`,
  `get_embedding_count`, `iter_all_embeddings` para que usen `conv_embeddings`.
- Actualizar `test_semantic_search.py` si hace setup de embeddings directamente.
- Test de migración: verificar que `init_convocatorias_db()` migra datos correctamente
  cuando la columna antigua existe.
- Benchmark: medir tiempos de analytics queries después de la migración.

### Paso 5: Documentación

- Actualizar `CLAUDE.md`: schema de la DB, nueva tabla `conv_embeddings`.
- Actualizar `SPEC.md`: si documenta el schema.

## Orden de ejecución

1. Paso 1 (migración embeddings) — el mayor impacto
2. Paso 4 (tests de la migración)
3. Paso 2 (covering indexes)
4. Benchmark y decidir si Paso 3 es necesario
5. Paso 5 (docs)

## Riesgos

- **VACUUM puede tardar varios minutos** en una DB de 5.6 GB. Solo ocurre una vez
  (primera ejecución post-migración). Considerar hacerlo offline o en el script de sync.
- **SQLite DROP COLUMN** requiere SQLite >= 3.35.0 (2021-03). Python 3.13 incluye SQLite 3.45+,
  así que no debería ser problema.
- **Espacio en disco temporal**: durante la migración coexistirán los datos en ambas ubicaciones.
  Necesita ~3.8 GB extra temporalmente.