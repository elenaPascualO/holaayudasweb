# Hola Ayudas — Especificaciones Tecnicas

## 1. Resumen

**Nombre del producto:** Hola Ayudas
**Version:** 0.4.0 (Fase 3 + Generacion automatica de posts RRSS)
**Proposito:** Interfaz web moderna y user-friendly para buscar ayudas y subvenciones publicas españolas a traves de la API publica de BDNS.

### 1.1 Vision
Ofrecer una forma rapida, bonita e intuitiva de buscar y explorar ayudas y subvenciones publicas del gobierno español, reemplazando el UX deficiente de infosubvenciones.es.

### 1.2 Integracion con HolaDatos
Los enlaces de Hola Ayudas se incluiran en las publicaciones de HolaDatos sobre ayudas, permitiendo a los usuarios buscar y explorar convocatorias relacionadas con una experiencia superior.

### 1.3 Estado Actual
Fase 3 completada. Replica local de convocatorias en SQLite, busqueda semantica con embeddings OpenAI, dashboard de analytics con Chart.js, y migracion local-first (SQLite como fuente primaria para busquedas, ultimas, y beneficiarios con fallback a BDNS). Ver `doc/ROADMAP.md` para detalle de fases y `doc/KILLER_PLAN.md` para el plan de replica + IA.

---

## 2. API Upstream: BDNS

### 2.1 Informacion General

| Aspecto | Detalle |
|---------|---------|
| **Base URL** | `https://www.infosubvenciones.es/bdnstrans/api/` |
| **Dominios alternativos** | `infosubvenciones.gob.es`, `pap.hacienda.gob.es`, `subvenciones.gob.es` |
| **Autenticacion** | Ninguna (publica) |
| **Formato de respuesta** | JSON (Spring Boot Page wrapper) |
| **Version backend** | 1.1.25 |
| **OpenAPI spec** | `doc/snpsap-api.json` (341 KB) |
| **Frescura de datos** | Actualizacion diaria (~06:30 CET) |
| **CORS** | No habilitado para dominios externos (requiere proxy) |

### 2.2 Estructura de Paginacion

Todos los endpoints paginados devuelven un wrapper Spring Boot Page:

```json
{
  "content": [...],
  "totalElements": 610576,
  "totalPages": 305288,
  "number": 0,
  "size": 50,
  "first": true,
  "last": false,
  "empty": false
}
```

- Las paginas son **0-indexed** (`page=0` es la primera)
- `pageSize` por defecto es 50

### 2.3 Endpoints de Busqueda

#### Convocatorias (Ayudas publicadas) — ~610.000 registros

**Busqueda:** `GET /convocatorias/busqueda`

| Parametro | Tipo | Descripcion |
|-----------|------|-------------|
| `vpd` | string | ID del portal (`GE` = general) |
| `page` | integer | Numero de pagina (0-based) |
| `pageSize` | integer | Items por pagina (default 50) |
| `order` | string | Campo de ordenacion |
| `direccion` | string | `asc` o `desc` |
| `descripcion` | string | Busqueda por texto en titulo |
| `descripcionTipoBusqueda` | integer | 0=exacta, 1=todas las palabras, 2=alguna palabra |
| `numeroConvocatoria` | string | Codigo BDNS |
| `fechaDesde` | string | Fecha inicio (`dd/mm/yyyy`) |
| `fechaHasta` | string | Fecha fin (`dd/mm/yyyy`) |
| `tipoAdministracion` | string | C=Central, A=Autonomica, L=Local, O=Otros |
| `organos` | array | IDs de organos |
| `regiones` | array | IDs de regiones |
| `mrr` | boolean | Filtro Mecanismo de Recuperacion y Resiliencia |

**Campos de respuesta por item:**
- `id`, `numeroConvocatoria`, `descripcion`, `descripcionLeng`
- `fechaRecepcion`, `nivel1`, `nivel2`, `nivel3`
- `mrr`, `codigoInvente`

**Ultimas:** `GET /convocatorias/ultimas` (mismos parametros, tope 10.000)

**Detalle:** `GET /convocatorias?vpd=GE&numConv=886707`

Campos del detalle:
- `codigoBDNS`, `descripcion`, `descripcionLeng`
- `organo` (objeto: `nivel1`, `nivel2`, `nivel3`)
- `sedeElectronica` (URL para tramitar)
- `fechaRecepcion`
- `instrumentos` (array)
- `tipoConvocatoria`
- `presupuestoTotal`
- `tiposBeneficiarios` (array)
- `sectores` (array con `descripcion`, `codigo`)
- `regiones` (array)
- `descripcionFinalidad`
- `descripcionBasesReguladoras`, `urlBasesReguladoras`
- `abierto` (boolean)
- `fechaInicioSolicitud`, `fechaFinSolicitud`
- `textInicio`, `textFin`
- `documentos` (array), `anuncios` (array)

#### Concesiones (Subvenciones otorgadas) — ~16.100.000 registros

**Busqueda:** `GET /concesiones/busqueda`

Campos de respuesta por item:
- `codConcesion`, `fechaConcesion`, `beneficiario`
- `instrumento`, `importe`, `ayudaEquivalente`
- `numeroConvocatoria`, `convocatoria`
- `nivel1`, `nivel2`, `nivel3`

#### Otros Endpoints de Busqueda

| Endpoint | Registros | Descripcion |
|----------|-----------|-------------|
| `GET /ayudasestado/busqueda` | ~6.000.000 | Ayudas de estado |
| `GET /minimis/busqueda` | ~4.200.000 | Ayudas de minimis |
| `GET /grandesbeneficiarios/busqueda` | ~126.000 | Grandes beneficiarios |
| `GET /partidospoliticos/busqueda` | ~5.700 | Subvenciones a partidos |
| `GET /sanciones/busqueda` | 4 | Sanciones |
| `GET /planesestrategicos/busqueda` | ~1.845 | Planes estrategicos |

### 2.4 Endpoints de Catalogos (sin paginacion, cache 24h)

| Endpoint | Items | Descripcion |
|----------|-------|-------------|
| `GET /regiones` | Arbol | Regiones NUTS (jerarquico) |
| `GET /finalidades?vpd=GE` | 22 | Categorias de finalidad |
| `GET /instrumentos` | 7 | Tipos de instrumento |
| `GET /actividades` | 22 | Sectores de actividad NACE |
| `GET /objetivos` | ~270 | Objetivos |
| `GET /reglamentos` | 8 | Reglamentos |
| `GET /sectores` | 25 | Sectores de producto |
| `GET /beneficiarios?vpd=GE` | 5 | Tipos de beneficiario |
| `GET /organos?vpd=GE&idAdmon=X` | Arbol | Organos por tipo de administracion |
| `GET /terceros?vpd=GE&busqueda=X` | Variable | Busqueda de terceros |

### 2.5 Limitaciones

| Limitacion | Impacto | Mitigacion |
|------------|---------|------------|
| Sin cabeceras CORS | No se puede llamar directamente desde el navegador | Proxy backend (FastAPI) |
| WAF bloquea POST | No se pueden usar POST para consultas complejas | Solo GET con query params |
| Formato de fecha `dd/mm/yyyy` | No estandar | Transformar en el backend |
| Paginas 0-indexed | Diferente a la convencion visual | Ajustar en el frontend |
| Sin endpoint de autocompletado | No hay sugerencias nativas | Cachear catalogos para filtrado local |
| Sin webhooks/streaming | No hay notificaciones push | Polling con cache |

---

## 3. Arquitectura Tecnica

### 3.1 Diagrama de Arquitectura

```
┌─────────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│                 │     │                      │     │                  │
│   Frontend      │────▶│   Backend/Proxy      │────▶│  API BDNS        │
│   Bun + Vite    │     │   Python/FastAPI      │     │  infosubvenciones│
│   Tailwind CSS  │     │   + Cache en memoria  │     │                  │
│   Vanilla JS    │     │   + SQLite local      │     │                  │
│   Chart.js      │     │   + OpenAI embeddings │     │                  │
└─────────────────┘     └───────────┬──────────┘     └──────────────────┘
                                    │
                        ┌───────────▼──────────┐
                        │  SQLite databases    │
                        │  ├── beneficiarios.db│
                        │  └── convocatorias.db│
                        │      + FTS5 index    │
                        │      + embeddings    │
                        └──────────────────────┘
```

### 3.2 Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Frontend Runtime | Bun |
| Frontend Build | Vite |
| Frontend Codigo | Vanilla JS (ES Modules) |
| Frontend Estilos | Tailwind CSS v4 |
| Frontend Testing | Vitest + jsdom |
| Backend Runtime | Python 3.13+ |
| Backend Framework | FastAPI |
| Backend Package Manager | uv |
| Backend Cliente HTTP | httpx |
| Backend Testing | pytest + httpx |
| Base de datos | SQLite (FTS5 + tabla separada para embeddings) |
| Embeddings | OpenAI text-embedding-3-small (1536 dims), almacenados en `conv_embeddings` |
| Vector ops | numpy (cosine similarity) |
| Deploy | Coolify en un servidor Hetzner |

### 3.3 API del Proxy Backend

El backend sirve datos desde la replica local SQLite como fuente primaria, con fallback automatico a la API BDNS upstream si la DB local esta vacia o falla. Ademas se encarga de:
- CORS (permite el origen del frontend)
- Cache (reduce carga en los servidores del gobierno para los pocos endpoints que aun usan BDNS directamente)
- Transformacion de formato de fecha (el frontend envia ISO, el backend convierte a `dd/mm/yyyy` para BDNS)
- Manejo de errores (traduce errores de BDNS a mensajes amigables)

#### Endpoints del Proxy

| Nuestro Endpoint | Upstream | Cache TTL |
|-----------------|----------|-----------|
| `GET /api/convocatorias` | SQLite local → fallback `/convocatorias/busqueda` | - |
| `GET /api/convocatorias/ultimas` | SQLite local → fallback `/convocatorias/ultimas` | - |
| `GET /api/convocatorias/:id` | SQLite local → fallback `/convocatorias?numConv=X` | 1 hora |
| `GET /api/concesiones` | `/concesiones/busqueda` | 5 min |
| `GET /api/beneficiarios-top` | SQLite local (todos los paths) → fallback `/grandesbeneficiarios/busqueda` | - |
| `GET /api/beneficiarios-top/anios` | SQLite local → fallback `/grandesbeneficiarios/anios` | - |
| `GET /api/catalogo/regiones` | `/regiones` | 24 horas |
| `GET /api/catalogo/finalidades` | `/finalidades?vpd=GE` | 24 horas |
| `GET /api/catalogo/instrumentos` | `/instrumentos` | 24 horas |
| `GET /api/catalogo/actividades` | `/actividades` | 24 horas |
| `GET /api/catalogo/beneficiarios` | `/beneficiarios?vpd=GE` | 24 horas |
| `POST /api/feedback` | - (local + Discord webhook) | - |
| `GET /api/health` | - | - |

#### Endpoints Propios (sin upstream)

| Endpoint | Fuente | Cache TTL |
|----------|--------|-----------|
| `GET /api/search` | Hibrida: FTS5 + FAISS + RRF (ver 3.5) | - |
| `GET /api/analytics/summary` | SQLite convocatorias | 1 hora |
| `GET /api/analytics/by-year` | SQLite convocatorias | 1 hora |
| `GET /api/analytics/monthly-trend` | SQLite convocatorias | 1 hora |
| `GET /api/analytics/by-theme` | SQLite convocatorias | 1 hora |
| `GET /api/analytics/by-region` | SQLite convocatorias | 1 hora |
| `GET /api/analytics/top-organs` | SQLite convocatorias | 1 hora |
| `GET /api/analytics/status` | SQLite convocatorias | 1 hora |
| `POST /api/admin/sync/convocatorias` | BDNS → SQLite (admin, background) | - |
| `GET /api/admin/sync/convocatorias/status` | Estado del sync en curso | - |
| `GET /api/admin/faiss/status` | Estado del indice vectorial FAISS | - |
| `GET /api/admin/posts` | Lista posts generados para RRSS (filtros: status, post_type) | - |
| `GET /api/admin/posts/:id` | Detalle de un post generado | - |
| `PATCH /api/admin/posts/:id` | Cambiar status de post (published/discarded) | - |
| `DELETE /api/admin/posts/:id` | Eliminar post generado | - |
| `POST /api/admin/posts/generate` | Generar post RRSS en background (6 tipos) | - |
| `GET /api/admin/posts/generate/status` | Estado de la generacion en curso | - |

### 3.4 Generacion de Posts para RRSS

Sistema semi-automatico que genera borradores de posts para X y LinkedIn a partir de la base de datos local de convocatorias, usando OpenAI (gpt-4o-mini) para el copywriting.

**Flujo:** Query DB → construir prompt → OpenAI genera dos versiones (X + LinkedIn) → guardar como draft → revisar manualmente → publicar.

#### Tipos de post

| Tipo | Param API | Descripcion | Query principal |
|------|-----------|-------------|-----------------|
| Ayuda destacada | `ayuda_destacada` | Destaca 1 ayuda abierta con alto presupuesto | Top por `presupuesto_total` DESC, abierta, no usada en posts anteriores |
| Datos de la semana | `datos_semana` | Resumen semanal de estadisticas | Count nuevas (7 dias), sum presupuesto, top region, top tema, total abiertas |
| Cierre inminente | `cierre_inminente` | Ayudas que cierran en los proximos 7 dias | `fecha_fin_solicitud` entre hoy y +7 dias, excluye fechas genericas `%-12-31` |
| Tematico | `tematico` | Agrupado por finalidad (ej: "5 ayudas para autonomos") | Finalidad con mas grants abiertas, no usada en los ultimos 30 dias |
| Top organismo | `top_organismo` | Que ministerio/CCAA publico mas ayudas esta semana | GROUP BY `nivel2` ultimos 7 dias, incluye ejemplos de convocatorias |
| Dato curioso | `dato_curioso` | Dato sorprendente de los datos historicos | Pool de 7 queries (record presupuesto, ano record, region top, etc.), rota para no repetir |

#### Formato de salida

Cada post se genera en dos versiones adaptadas a la plataforma:

| Plataforma | Longitud | Tono | Formato |
|------------|----------|------|---------|
| X | 300-600 chars | Informal, directo | 2-3 hashtags, enlace a holaayudas.com |
| LinkedIn | 800-1500 chars | Profesional, contexto | Estructura con saltos de linea, 3-5 hashtags |

#### Uso via API

```bash
# Generar post (auto-selecciona tipo segun rotacion)
POST /api/admin/posts/generate?post_type=auto

# Generar tipo especifico
POST /api/admin/posts/generate?post_type=ayuda_destacada

# Ver drafts pendientes
GET /api/admin/posts?status=draft

# Marcar como publicado
PATCH /api/admin/posts/1  {"status": "published"}

# Descartar
PATCH /api/admin/posts/1  {"status": "discarded"}
```

Todos los endpoints requieren `Authorization: Bearer $ADMIN_SECRET`.

#### Uso via CLI

```bash
uv run python -m backend.scripts.generate_posts              # auto
uv run python -m backend.scripts.generate_posts ayuda_destacada
uv run python -m backend.scripts.generate_posts dato_curioso
```

#### Auto-rotacion (`post_type=auto`)

Prioridad: `cierre_inminente` (si hay grants cerrando) → `datos_semana` (lun-mie) → `top_organismo` → `ayuda_destacada` → `dato_curioso` → `tematico`. Evita repetir tipos generados en los ultimos 7 dias.

### 3.5 Estrategia de Busqueda Hibrida (FTS5 + FAISS + RRF)

La busqueda en `/api/search` combina dos sistemas complementarios fusionados con
Reciprocal Rank Fusion (RRF):

**Componentes:**

1. **FTS5 (keywords):** Busqueda textual en SQLite FTS5 con tokenizacion unicode61
   (sin acentos). Encuentra coincidencias exactas por palabras. Rapido (~5ms).

2. **FAISS (semantica):** Indice vectorial en memoria (FAISS, de Meta) con embeddings
   de OpenAI `text-embedding-3-small` (1536 dims). Busca por significado sobre todo
   el corpus (~600K convocatorias). Usa `OPQ64,IVF{nlist},PQ64` para eficiencia de
   memoria (~40 MB) con `nprobe=32`.

3. **RRF (fusion):** Reciprocal Rank Fusion combina ambas listas rankeadas.
   Documentos que aparecen en ambas listas suben al top.
   Formula: `score(d) = sum(1/(k + rank))` con `k=60`.

**Flujo:**
```
query → FTS5 (500 candidatos) ──┐
                                ├─→ RRF fusion → filtros → top_k
query → OpenAI embed → FAISS   ─┘
         (500 candidatos)
```

**Fallbacks:**
- FAISS no listo (arranque): solo FTS5
- OpenAI falla: solo FTS5
- FTS5 vacio + FAISS con resultados: solo FAISS
- Ambos vacios: 0 resultados

**Threshold:** Score minimo de cosine similarity = 0.25 para resultados FAISS.

**Carga del indice:** Se construye en background al arrancar la app usando una
estrategia de 2 pasadas con memoria constante (~400 MB pico en vez de ~7 GB):
1. Pasada 1: carga un sample aleatorio de 50K vectores de SQLite para entrenar el indice
2. Pasada 2: itera todos los embeddings en batches de 10K y los añade al indice entrenado
Se refresca tras cada sync de embeddings. La busqueda funciona en modo FTS5-only
mientras FAISS carga.

**Archivos clave:**
- `backend/services/faiss_index.py` — Gestion del indice FAISS
- `backend/services/semantic_search.py` — Logica de busqueda hibrida + RRF
- `backend/services/embeddings.py` — Cliente OpenAI + conversion BLOB
- `backend/services/convocatorias_db.py` — FTS5 + tabla `conv_embeddings`

---

## 4. Funcionalidades del Frontend (MVP)

### 4.1 Pagina Principal
- Barra de busqueda con input de texto
- Chips de filtro rapido (Autonomos, PYMEs, Educacion, Cultura, I+D, Empleo, Digitalizacion, Agricultura)
- Feed de ultimas ayudas publicadas con paginacion
- Panel lateral de filtros (estado, tipo de administracion, rango de fechas)

### 4.2 Resultados de Busqueda
- Resultados paginados (scroll infinito o paginacion)
- Cada resultado: titulo, convocante, fecha, estado (abierta/cerrada)
- Barra lateral de filtros: tipo de administracion, region, rango de fechas, tipo de beneficiario

### 4.3 Detalle de Convocatoria
- Vista completa estructurada de la informacion
- Indicador de estado (abierta/cerrada/proxima)
- Plazo de solicitud con cuenta atras visual
- Enlace directo a la sede electronica para tramitar
- Documentos descargables
- Enlace para ver beneficiarios (concesiones)

### 4.4 Deep Linking
- URLs tipo `/ayuda/886707` para enlazar directamente desde HolaDatos
- Meta tags SEO por convocatoria

---

## 5. Configuracion

### 5.1 Configuracion del Backend

| Setting | Default | Descripcion |
|---------|---------|-------------|
| `BDNS_BASE_URL` | `https://www.infosubvenciones.es/bdnstrans/api` | API upstream |
| `CACHE_TTL_CATALOGS` | 86400 (24h) | TTL cache catalogos en segundos |
| `CACHE_TTL_SEARCH` | 300 (5min) | TTL cache busquedas |
| `CACHE_TTL_DETAIL` | 3600 (1h) | TTL cache detalle |
| `BDNS_TIMEOUT` | 30.0 | Timeout HTTP para peticiones a BDNS (segundos) |
| `ALLOWED_ORIGINS` | `http://localhost:5174` | Origenes CORS |
| `ENVIRONMENT` | `development` | `development` o `production` |
| `CONVOCATORIAS_DB_PATH` | `data/convocatorias.db` | Ruta a la BD SQLite de convocatorias |
| `OPENAI_API_KEY` | _(vacio)_ | API key de OpenAI para embeddings y generacion de posts |
| `POSTS_OPENAI_MODEL` | `gpt-4o-mini` | Modelo OpenAI para generacion de posts RRSS |
| `DISCORD_WEBHOOK_URL` | _(vacio)_ | Webhook de Discord para notificaciones de feedback |

### 5.2 Configuracion CORS

#### Desarrollo
```python
CORS_ORIGINS = [
    "http://localhost:5174",
    "http://localhost:8001",
    "http://127.0.0.1:5174",
]
```

#### Produccion
```python
CORS_ORIGINS = [
    "https://www.holaayudas.com",
]
```

---

## 6. Seguridad

### 6.1 Medidas

| Categoria | Medida |
|----------|---------|
| CORS | Restringir a origenes conocidos |
| Rate Limiting | Limitar peticiones para proteger la API upstream |
| Validacion de Input | Sanitizar todos los query parameters |
| Cabeceras | Cabeceras de seguridad (X-Content-Type-Options, X-Frame-Options, etc.) |
| Rate Limiting Feedback | 5 envios/hora por IP en POST /api/feedback |
| Sin almacenamiento | Solo proxy, no se guardan datos de usuario (excepto feedback) |
| Manejo de errores | Nunca exponer errores upstream ni stack traces al usuario |

### 6.2 Rate Limiting

#### BDNS Upstream (Implementado)
- Semaforo global que limita a 5 peticiones concurrentes a BDNS
- Reintentos automaticos con backoff exponencial ante respuestas 429
- Maximo 2 reintentos por peticion

#### Feedback (Implementado)
- 5 envios/hora por IP en `POST /api/feedback`

#### Endpoints proxy (Planificado)

| Endpoint | Limite | Ventana |
|----------|--------|---------|
| `/api/convocatorias` | 30 req | 1 minuto |
| `/api/convocatorias/:id` | 60 req | 1 minuto |
| `/api/catalogo/*` | 10 req | 1 minuto |
| Global | 100 req | 1 minuto |

---

## 7. Despliegue

### 7.1 Plataforma
Coolify en un servidor Hetzner (`ubuntu-8gb-hel1-1`: 8 GB de RAM, 4 vCPU). Despliegue manual con el botón **Deploy** de Coolify (push a `master` no despliega). Operación detallada en `doc/OPERACIONES.md`.

### 7.2 Build
Dockerfile con multi-stage build:
1. Stage 1: Bun construye el frontend (`frontend/dist/`)
2. Stage 2: Python sirve el backend + frontend estatico

### 7.3 Variables de Entorno

```bash
ENVIRONMENT=production
ALLOWED_ORIGINS=https://www.holaayudas.com
BDNS_BASE_URL=https://www.infosubvenciones.es/bdnstrans/api
```

---

## Historial del Documento

| Version | Fecha | Cambios |
|---------|-------|---------|
| 0.1.0 | 2026-02 | Especificaciones iniciales a partir del estudio de viabilidad |
| 0.1.1 | 2026-02 | Feedback via Discord webhook, rate limiter BDNS, timeout configurable |
| 0.1.2 | 2026-02 | Homepage rediseñada con filtros y paginacion, quick filters en pagina de busqueda, puertos dev actualizados (8001/5174) |
| 0.2.0 | 2026-02 | Fase 2: Transparencia (grandes beneficiarios, SQLite FTS5 para beneficiarios) |
| 0.3.0 | 2026-03 | Fase 3: Replica local convocatorias en SQLite, busqueda semantica (OpenAI embeddings + numpy coseno), dashboard analytics (Chart.js), nuevos endpoints /api/search y /api/analytics/* |
| 0.3.1 | 2026-03 | Sync en background: POST /sync/convocatorias lanza tarea async y retorna inmediatamente, nuevo GET /sync/convocatorias/status para monitorizar progreso |
| 0.3.2 | 2026-03 | Migracion local-first: busqueda, ultimas y beneficiarios servidos desde SQLite local con fallback a BDNS. Fix _row_to_search_result() para exponer nivel1/nivel2/nivel3 como campos top-level |
| 0.3.3 | 2026-03 | Fix drill-down desde graficas de analytics: nuevos filtros `descripcionFinalidad` y `regionDesc` en `/api/convocatorias`, status chart usa `estado` en vez de `abierto` |
| 0.3.4 | 2026-03 | Busqueda hibrida FAISS+FTS5+RRF: indice vectorial FAISS en memoria reemplaza coseno numpy. Embeddings migrados a tabla separada `conv_embeddings` para reducir I/O en queries analytics (~21s → <1s). Covering indexes para analytics |
| 0.4.0 | 2026-03 | Generacion automatica de posts para RRSS: tabla `generated_posts` en convocatorias.db, script CLI `generate_posts.py` con 6 tipos de post (ayuda_destacada, datos_semana, cierre_inminente, tematico, top_organismo, dato_curioso), OpenAI gpt-4o-mini para copywriting (X + LinkedIn), endpoints admin para gestion de drafts |
| 0.4.1 | 2026-04 | Fix FAISS OOM en produccion: carga del indice vectorial con estrategia de 2 pasadas y memoria constante (~400 MB pico vs ~7 GB anterior). Nueva funcion `sample_embeddings()` para training sample via SQL |
