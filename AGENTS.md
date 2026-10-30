# AGENTS.md — Hola Ayudas

Contexto del proyecto para agentes de código (Claude Code, Codex, etc.).

## Qué es

Web gratuita para buscar ayudas y subvenciones públicas españolas (www.holaayudas.com). Los datos vienen de la API pública de la **BDNS** (infosubvenciones.es). Mantiene una réplica local de ~659K convocatorias en SQLite con búsqueda por palabras clave (FTS5) y semántica (embeddings de OpenAI + FAISS).

Idioma: la UI, los textos y la documentación (`doc/`) están en **español**. El código, los identificadores y los mensajes de commit, en inglés.

## Flujo de trabajo obligatorio: spec → tests → código

**No se toca código de producción sin una spec aprobada.** Para cualquier funcionalidad nueva o cambio de comportamiento:

1. **Spec primero.** Crear `doc/tasks/<nombre-en-kebab-case>.md` con: contexto/problema, objetivo, diseño (flujos, archivos afectados, cambios de API/configuración), qué queda fuera de alcance, **la lista de tests** (nombre y qué comprueba cada uno) y cómo verificarlo en producción. Formato de referencia: `doc/tasks/faiss-persistence.md`. Presentar la spec al usuario antes de continuar.
2. **Tests de la spec.** Escribir los tests listados en la spec antes de la implementación. Deben fallar por la razón esperada (la funcionalidad aún no existe).
3. **Implementación.** Escribir el código hasta que pasen los tests de la spec. Si durante la implementación cambia el diseño, actualizar la spec (y sus tests) en vez de dejarla desfasada.
4. **Validación.** Una spec solo se da por válida cuando **toda la suite está en verde**, no solo los tests nuevos:
   ```bash
   uv run pytest                     # backend: todos
   cd frontend && bun run test:run   # frontend: todos
   ```
   Si algún test falla, aunque parezca no relacionado, se investiga y se arregla antes de dar la spec por terminada. Nunca se desactivan ni se debilitan tests para que pasen. Anotar en la spec el estado y el resultado de la suite.

Excepciones (no requieren spec): erratas, cambios solo de documentación y arreglos triviales de una línea sin cambio de comportamiento. Aun así, la suite completa debe pasar.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.13, FastAPI, httpx, SQLite (FTS5), FAISS (`faiss-cpu`), numpy, OpenAI SDK |
| Frontend | Vanilla JS (ES modules), Vite, Tailwind CSS v4, router propio con History API |
| Gestores | `uv` (Python), `bun` (frontend) |
| Tests | pytest + pytest-asyncio (`asyncio_mode = auto`), Vitest + jsdom |
| Lint | ruff (`line-length = 100`) |
| Deploy | Un solo contenedor Docker en **Coolify** (Hetzner). Puerto 8000. Datos en volumen `/app/data` |

> El `README.md` y algunos docs antiguos mencionan Railway: está desactualizado, ahora es Coolify.

## Estructura

```
backend/
  main.py            App FastAPI: lifespan (init BDs, carga FAISS en background), middlewares
                     (security headers, redirección a www en prod, CORS), sirve frontend/dist
  config.py          Toda la configuración vía variables de entorno (+ .env en la raíz)
  routes/            Un router por área: convocatorias, semantic (/api/search), admin (syncs,
                     FAISS), posts (admin), analytics, beneficiarios, concesiones, catalogs,
                     feedback, seo (sitemaps, robots, HTML con meta server-side)
  services/          bdns_client (proxy + caché + reintentos), convocatorias_db / beneficiarios_db /
                     posts_db (SQLite), embeddings, faiss_index, semantic_search (FTS + FAISS + RRF),
                     cache (en memoria), rate_limiter, email_notify, seo
  scripts/           sync_convocatorias, sync_beneficiarios, generate_posts
                     (ejecutables con `uv run python -m backend.scripts.<nombre>` o vía /api/admin)
  tests/             pytest; conftest pone TESTING=1 para no cargar FAISS
frontend/
  src/main.js, router.js, pages/, components/, utils/ (api.js = cliente del backend)
  tests/             Vitest
doc/                 SPEC, ROADMAP, SEO, OPERACIONES (runbook), tasks/
data/                SQLite locales (no se versionan)
```

## Comandos

```bash
uv sync                                               # deps backend
cd frontend && bun install                            # deps frontend

uv run uvicorn backend.main:app --reload --port 8001  # backend dev (Vite hace proxy a 8001)
cd frontend && bun run dev                            # frontend dev en :5174, proxy /api -> :8001

uv run pytest -v                                      # tests backend
cd frontend && bun run test:run                       # tests frontend
uv run ruff check backend                             # lint

docker build -t holaayudas . && docker run -p 8000:8000 holaayudas
```

## Conceptos clave

- **Dos fuentes de datos**: la búsqueda principal (`/api/convocatorias`) y analytics leen de la **réplica SQLite local**. El detalle, los catálogos y las concesiones pasan por `bdns_client` (proxy a BDNS con caché en memoria y semáforo de concurrencia).
- **Búsqueda semántica** (`/api/search`, `services/semantic_search.py`): FTS5 + FAISS fusionados con Reciprocal Rank Fusion. Si OpenAI o FAISS fallan, **degrada en silencio** a solo FTS. Los filtros se aplican después del ranking.
- **FAISS** (`services/faiss_index.py`): índice `OPQ64,IVF1024,PQ64` en memoria, **persistido en disco** (`FAISS_INDEX_PATH`, por defecto `/app/data/faiss.index` + `.meta.json`). SQLite es la fuente de verdad y el archivo es una caché.
  - `load_or_build()` (arranque): lee el archivo y añade los embeddings que falten. Solo construye desde cero si no hay archivo o es incompatible.
  - `sync_from_db()` (tras los syncs `daily` / `backfill-embeddings`): añade los vectores nuevos sin reentrenar y guarda.
  - `load_index_from_db()` (`POST /api/admin/faiss/rebuild`): reentrenamiento completo.
  - Todas las escrituras van serializadas por `_write_lock`. Una construcción completa tarda más de 12 min y llega a ~5 GB de RSS en un servidor de 8 GB: **nunca debe haber dos a la vez** (ya pasó: hubo un bucle de OOM, ver `ad4af49`). Cuidado con cualquier cambio que suba el consumo de memoria o que añada caminos de reconstrucción.
- **Embeddings**: `text-embedding-3-small` (1536 dims), guardados como BLOB float32 en `conv_embeddings`. Solo se generan para convocatorias con `detail_fetched = 1`.
- **Syncs** (`scripts/sync_convocatorias.py`): modos `daily`, `full-list`, `backfill-detail`, `backfill-embeddings`. Se lanzan desde `POST /api/admin/sync/convocatorias?mode=…` como `asyncio.Task` en segundo plano. El estado está **en memoria** y se pierde al reiniciar. Los fallos envían email si SMTP está configurado.
- **Admin**: todos los endpoints de `/api/admin/*` requieren `Authorization: Bearer $ADMIN_SECRET` (comparación con `hmac.compare_digest`) y tienen rate limit.
- **SEO**: es importante para el proyecto. Las páginas tienen meta, H1, JSON-LD y HTML server-side inyectado (`services/seo.py`, `routes/seo.py`). Hay un test de completitud SEO; si añades páginas, actualízalo junto con el sitemap. Ver `doc/SEO.md`.
- **Producción** (`ENVIRONMENT=production`): redirección 301 a `www`, HSTS, `/docs` desactivado.

## Convenciones

- Python: type hints, docstrings estilo Google (`Args:` / `Returns:`), `logging` por módulo (`logger = logging.getLogger(__name__)`), imports perezosos para dependencias pesadas (`openai`, `faiss`) dentro de funciones cuando ya se hace así.
- La configuración nueva va en `backend/config.py` leyendo de `os.getenv`, y se documenta en `doc/OPERACIONES.md`.
- SQLite: abrir con `_get_connection()` y cerrar en `finally`.
- **Nunca llamar a SQLite, FAISS ni nada lento de forma síncrona dentro de una ruta `async def`**: bloquea el event loop y para **todo** el servidor. Usar `await asyncio.to_thread(func, ...)` o un wrapper `*_async`. Cada ruta nueva con trabajo síncrono necesita su test en `backend/tests/test_non_blocking.py`. Ver `doc/tasks/non-blocking-routes.md`.
- **No ejecutar `ANALYZE` en la BD.** Los índices de los sitemaps (`idx_conv_sitemap_cover`, `idx_conv_sitemap_fin_cover`) están ajustados para el planificador sin estadísticas; con ellas cambia los planes. Ver `doc/tasks/sitemap-covering-index.md`.
- Frontend: vanilla JS sin framework, componentes como funciones que devuelven HTML/DOM, y llamadas al backend solo a través de `utils/api.js`.
- Commits: Conventional Commits en inglés (`feat:`, `fix:`, `test:`…).
- No commitear `.env` ni `data/*.db`.

## Operación

Despliegue, variables de entorno, syncs, backfills, OpenAI (keys, billing) y resolución de problemas: **`doc/OPERACIONES.md`**. Mantenlo actualizado cuando cambie algo operativo (nuevas variables, endpoints de admin, modos de sync).
