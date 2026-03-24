# Busqueda Hibrida: FAISS + FTS5 + RRF

## Contexto

La busqueda "semantica" actual es en realidad un pre-filtro FTS5 + re-ranking con numpy.
Solo compara contra los candidatos que FTS5 encontro por palabras (500) o contra 5000
convocatorias recientes — de ~600K totales. Si el usuario busca con lenguaje natural que
no coincide textualmente, pierde el 99% del corpus. Esto anula el valor de la busqueda
semantica, que es la razon principal de existencia de la app.

**Objetivo:** Busqueda hibrida real que combine FTS5 (keywords) + FAISS (semantica sobre
todo el corpus) fusionados con Reciprocal Rank Fusion (RRF).

## Arquitectura Nueva

```
Usuario busca "ayudas para emprendedores jovenes"
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
   FTS5 (keywords)      FAISS (semantica)
   "emprendedores"       embedding query
   "jovenes"             vs 600K embeddings
   → 500 candidatos      → 500 candidatos
   ranked by BM25        ranked by cosine sim
         │                     │
         └──────────┬──────────┘
                    ▼
            RRF Fusion (k=60)
            docs en ambas listas → top
            docs solo FTS → medio
            docs solo FAISS → bajo
                    │
                    ▼
            Filtros (año, estado)
                    │
                    ▼
            Top K resultados
```

## Plan de Implementacion

### Paso 1: Dependencia `faiss-cpu`

**Archivo:** `pyproject.toml`

Anadir `faiss-cpu>=1.8.0` a dependencies.

---

### Paso 2: Nuevo modulo `backend/services/faiss_index.py`

Modulo que gestiona el indice FAISS en memoria.

**Estado global:**
- `_index: faiss.Index | None` — el indice FAISS
- `_ready: bool` — indica si el indice esta listo para queries
- `_lock: threading.Lock` — protege escrituras concurrentes

**Funciones:**

```python
def is_ready() -> bool
    """Check if FAISS index is loaded and ready for queries."""

def load_index_from_db(db_path: str | None = None) -> None
    """Load all embeddings from SQLite and build FAISS index.

    - Lee embeddings en batches de 10K via iter_all_embeddings()
    - Si hay suficientes vectores (>= 10K): construye OPQ64,IVF1024,PQ64
      (entrena con sample de 50K, nprobe=32)
    - Si hay pocos vectores (< 10K): usa IndexFlatIP (brute force, OK a esa escala)
    - Sets _ready = True al terminar
    """

def search(query_vec: np.ndarray, k: int = 500) -> list[tuple[int, float]]
    """Search FAISS index for nearest neighbors.

    Returns: [(convocatoria_id, cosine_similarity), ...] sorted by similarity desc.
    Returns [] if not ready.
    """

def add_vectors(ids: list[int], vectors: np.ndarray) -> None
    """Incremental add after sync. Thread-safe."""

def get_stats() -> dict
    """Returns {ready, total_vectors, index_type}."""
```

**Nota sobre metricas:** Los embeddings de OpenAI ya estan L2-normalizados, por lo que
usamos inner product (IP) como metrica — equivalente a cosine similarity para vectores
normalizados.

**Memoria:** OPQ64,IVF1024,PQ64 con 600K vectores ≈ 40 MB.
En CX33 (8 GB RAM) deja >7 GB libres.

---

### Paso 3: Funciones auxiliares en `backend/services/convocatorias_db.py`

**Nuevas funciones:**

```python
def iter_all_embeddings(batch_size: int = 10000, db_path: str | None = None)
    -> Iterator[list[tuple[int, bytes]]]:
    """Yield batches of (id, embedding_blob) for FAISS index building."""

def get_convocatorias_by_ids(ids: list[int], db_path: str | None = None)
    -> dict[int, dict]:
    """Fetch metadata for a list of IDs.
    Needed to hydrate FAISS-only results (not in FTS results)."""

def get_embedding_count(db_path: str | None = None) -> int:
    """Count of records with non-null embeddings."""
```

**Funcion a eliminar:** `get_recent_with_embeddings()` — ya no es necesaria.

**Funcion `search_fts` — optimizar:** Dejar de seleccionar `c.embedding` en la query
ya que no se necesita para el flujo RRF (FAISS se encarga del ranking semantico).

---

### Paso 4: Reescribir `backend/services/semantic_search.py`

**Nuevo flujo de `semantic_search()`:**

```python
async def semantic_search(
    query: str,
    filters: dict | None = None,
    top_k: int = 20,
    fts_candidates: int = 500,
    faiss_candidates: int = 500,
    rrf_k: int = 60,
    similarity_threshold: float = 0.25,
) -> dict:
```

1. **FTS5:** `search_fts(query, limit=fts_candidates)` → lista rankeada por BM25
2. **FAISS** (si `is_ready()`):
   - Embed query via OpenAI → `query_vec`
   - `faiss_index.search(query_vec, k=faiss_candidates)` → lista rankeada por cosine sim
   - Filtrar por `similarity_threshold`
3. **RRF fusion:**
   ```python
   def reciprocal_rank_fusion(fts_ids, faiss_ids, k=60):
       scores = {}
       for rank, doc_id in enumerate(fts_ids, 1):
           scores[doc_id] = scores.get(doc_id, 0) + 1/(k + rank)
       for rank, doc_id in enumerate(faiss_ids, 1):
           scores[doc_id] = scores.get(doc_id, 0) + 1/(k + rank)
       return sorted(scores.items(), key=lambda x: x[1], reverse=True)
   ```
4. **Hidratar metadata:** Para IDs que solo vienen de FAISS (no estan en FTS results),
   llamar a `get_convocatorias_by_ids()`.
5. **Filtrar** por año/estado despues del ranking.
6. **Devolver** top_k con `_score` = RRF score normalizado.

**Fallbacks:**
- FAISS no ready → solo FTS5 (degradacion graceful)
- OpenAI falla → solo FTS5
- FTS5 devuelve 0 + FAISS tiene resultados → solo FAISS
- Ambos devuelven 0 → empty state

**Tambien actualizar `keyword_trend()`:** Reemplazar `get_recent_with_embeddings()` con
`faiss_index.search()` para cubrir todo el corpus.

**Eliminar:** `_cosine_similarity_batch()`, imports de `blob_to_embedding` (se mueve a faiss_index).

---

### Paso 5: Carga FAISS en startup (`backend/main.py`)

Modificar lifespan para cargar FAISS en background (no bloquea el arranque):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_convocatorias_db()
    load_index_template(frontend_dist)

    # FAISS loads in background — search works FTS-only until ready
    faiss_load_task = asyncio.create_task(
        asyncio.to_thread(faiss_index.load_index_from_db)
    )

    yield

    faiss_load_task.cancel()
    cancel_sync_task()
    await close_client()
```

**Tiempo estimado de carga:** 15-30s para leer 600K BLOBs y construir indice.
Durante ese tiempo, `/api/search` funciona con FTS5-only.

---

### Paso 6: Actualizacion incremental tras sync (`backend/routes/admin.py`)

Despues de que el sync de embeddings termine, actualizar el indice FAISS:

```python
# En _run_sync_background(), despues de completar sync:
if faiss_index.is_ready():
    await asyncio.to_thread(faiss_index.add_vectors, new_ids, new_vecs)
```

Tambien anadir endpoint de status:

```python
@router.get("/faiss/status")
async def get_faiss_status(authorization: str = Header(...)) -> dict:
    _validate_token(authorization)
    return faiss_index.get_stats()
```

---

### Paso 7: Tests

**Modificar:** `backend/tests/test_semantic_search.py`
- Mock `faiss_index.is_ready()` y `faiss_index.search()`
- Test RRF fusion con resultados de ambas fuentes
- Test degradacion graceful (FAISS no ready)
- Test deduplicacion (mismo doc en FTS y FAISS sube de score)

**Nuevo:** `backend/tests/test_faiss_index.py`
- Test build + search con indice pequeno (flat, no IVF)
- Test `add_vectors` incremental
- Test `is_ready()` antes y despues de carga

---

### Paso 8: Limpieza

- Eliminar `get_recent_with_embeddings()` de `convocatorias_db.py`
- Eliminar `_cosine_similarity_batch()` de `semantic_search.py`
- Eliminar seleccion de `c.embedding` en `search_fts()` (ya no necesario)

---

## Orden de Implementacion

1. `pyproject.toml` — dependencia
2. `backend/services/faiss_index.py` — nuevo modulo (autocontenido)
3. `backend/services/convocatorias_db.py` — nuevas funciones + optimizar search_fts
4. `backend/services/semantic_search.py` — reescribir con RRF
5. `backend/main.py` — carga FAISS en background
6. `backend/routes/admin.py` — hook post-sync + endpoint status
7. Tests
8. Limpieza de codigo muerto

## Verificacion

1. `uv sync` — instalar faiss-cpu
2. `uv run pytest -v` — todos los tests pasan
3. Arrancar backend: `uv run uvicorn backend.main:app --reload --port 8001`
   - Verificar en logs que FAISS carga en background
   - Verificar que `/api/search?q=galizuela` devuelve 0 resultados
   - Verificar que `/api/search?q=digitalización+pymes` devuelve resultados relevantes
   - Verificar que `/api/search?q=ayudas+para+hacer+mi+negocio+más+tecnológico` devuelve
     resultados de digitalizacion (busqueda semantica pura, sin match FTS)
4. Frontend: buscar en `/buscar` con terminos naturales, verificar UX