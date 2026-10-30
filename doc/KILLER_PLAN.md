# Plan Killer: Réplica Local BDNS + IA + Alertas Semánticas

## Contexto

Hola Ayudas es actualmente un proxy con cache hacia la API pública de BDNS. Funciona bien para buscar y consultar, pero depende 100% de la API upstream, no permite analytics propias, y no ofrece ningún valor añadido sobre los datos brutos.

Este plan evalúa la evolución hacia un **producto con datos propios y inteligencia**: replicar la BDNS localmente, enriquecerla con IA, y ofrecer alertas semánticas. Se compara con la alternativa ligera de simplemente enlazar al sistema de alertas de infosubvenciones.

---

## Comparativa: Camino Killer vs Enlazar con Infosubvenciones

### Opción A: Enlazar con alertas de infosubvenciones

| | |
|---|---|
| **Qué es** | Añadir un botón/enlace en Hola Ayudas que lleve al usuario a configurar alertas en la web oficial de infosubvenciones |
| **Esfuerzo** | 1 hora (un enlace + texto explicativo) |
| **Coste operativo** | $0 |
| **RGPD** | Ninguno (los datos los gestiona el gobierno) |
| **Valor para el usuario** | Bajo — la UX de infosubvenciones es mala, los filtros son básicos |
| **Valor diferencial** | Ninguno — cualquier web puede hacer esto |
| **Mantenimiento** | Zero |
| **Riesgo** | Zero |

**Veredicto**: solución pragmática si no se quiere invertir. No aporta nada al producto.

### Opción B: El camino killer (réplica + IA + alertas)

| | |
|---|---|
| **Qué es** | Base de datos propia de convocatorias, enriquecida con etiquetas IA, con búsqueda semántica y alertas inteligentes |
| **Esfuerzo** | 3-6 semanas (incremental, valor desde la semana 1) |
| **Coste operativo** | Servidor Hetzner existente + email service + API IA incremental |
| **RGPD** | Mínimo si no hay cuentas de usuario; medio si hay alertas email |
| **Valor para el usuario** | Muy alto — búsqueda en lenguaje natural, resúmenes, alertas inteligentes |
| **Valor diferencial** | Enorme — infosubvenciones nunca tendrá esto |
| **Mantenimiento** | Medio — sync diario, monitoreo de calidad IA |
| **Riesgo** | Medio — dependencia de API BDNS para sync, coste IA si escala |

**Veredicto**: transforma Hola Ayudas de un "frontend bonito" a un **producto con inteligencia propia**.

---

## El Camino Killer: Plan de Implementación por Fases

### Visión de arquitectura final

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (SPA)                        │
│  Búsqueda semántica │ Analytics dashboard │ Alertas UI  │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                   FASTAPI BACKEND                        │
│                                                          │
│  /api/convocatorias ──► SQLite local (FTS5 + semántica) │
│  /api/analytics ──────► Queries sobre réplica local      │
│  /api/alertas ────────► Suscripciones + email digest     │
│  /api/rss ────────────► Feed XML generado desde local    │
│                                                          │
│  Servicios:                                              │
│  ├── convocatorias_db.py  (SQLite réplica + FTS5)       │
│  ├── ai_enrichment.py     (Claude API → etiquetas)      │
│  ├── semantic_search.py   (embeddings + similitud)      │
│  └── alerts_service.py    (check + email)               │
│                                                          │
│  Cron jobs (Coolify Scheduled Tasks):                    │
│  ├── sync_convocatorias   (diario, ~10min)              │
│  ├── enrich_new           (diario, tras sync)           │
│  └── send_alerts          (diario/semanal)              │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│              SQLite (data/convocatorias.db)              │
│                                                          │
│  convocatorias (610K filas, ~600MB)                      │
│  ├── datos BDNS: código, descripción, fechas, org...    │
│  ├── etiquetas IA: categorías, resumen, keywords        │
│  └── embedding: vector 384/768-dim para similitud       │
│                                                          │
│  convocatorias_fts (FTS5 virtual table)                  │
│  alert_subscriptions (email + filtros, sin auth)         │
│  sync_metadata (timestamps de última sincronización)     │
└─────────────────────────────────────────────────────────┘
```

---

### FASE 1: Réplica de Convocatorias en SQLite (~3 días) — COMPLETADA

**Objetivo**: Tener todas las convocatorias de BDNS en una base de datos local con búsqueda FTS5.

**Por qué primero**: Es la base para todo lo demás (IA, analytics, alertas). Sin réplica local, cada feature depende de la API upstream.

#### 1.1 Esquema SQLite

```sql
-- Tabla principal
CREATE TABLE convocatorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bdns_code TEXT NOT NULL UNIQUE,
    descripcion TEXT NOT NULL,
    descripcion_leng TEXT,               -- idioma cooficial
    fecha_recepcion TEXT NOT NULL,        -- YYYY-MM-DD
    nivel1 TEXT,                          -- organismo nivel 1
    nivel2 TEXT,                          -- organismo nivel 2
    nivel3 TEXT,                          -- organismo nivel 3
    presupuesto_total REAL,
    tipo_convocatoria TEXT,
    finalidad TEXT,                       -- descripción finalidad
    abierto INTEGER,                      -- 0/1 boolean
    fecha_inicio_solicitud TEXT,
    fecha_fin_solicitud TEXT,
    sede_electronica TEXT,
    regiones TEXT,                        -- JSON array
    instrumentos TEXT,                    -- JSON array
    tipos_beneficiarios TEXT,             -- JSON array
    sectores TEXT,                        -- JSON array
    url_bases_reguladoras TEXT,
    mrr INTEGER DEFAULT 0,               -- mecanismo recuperación
    -- Columnas IA (Fase 2, NULL inicialmente)
    ai_categories TEXT,                   -- JSON array de categorías semánticas
    ai_summary TEXT,                      -- resumen en lenguaje ciudadano
    ai_target_audience TEXT,              -- público objetivo simplificado
    ai_keywords TEXT,                     -- keywords para búsqueda/SEO
    ai_difficulty TEXT,                   -- fácil/media/difícil
    ai_processed_at TEXT,                 -- timestamp de procesamiento IA
    embedding BLOB,                       -- vector float32 (Fase 2)
    -- Metadata
    detail_fetched INTEGER DEFAULT 0,     -- 1 si hemos cargado el detalle completo
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_conv_bdns ON convocatorias(bdns_code);
CREATE INDEX idx_conv_fecha ON convocatorias(fecha_recepcion DESC);
CREATE INDEX idx_conv_abierto ON convocatorias(abierto);
CREATE INDEX idx_conv_ai ON convocatorias(ai_processed_at);

-- FTS5 para búsqueda de texto
CREATE VIRTUAL TABLE convocatorias_fts USING fts5(
    descripcion,
    finalidad,
    nivel1,
    nivel2,
    ai_summary,
    ai_keywords,
    content='convocatorias',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

-- Triggers para mantener FTS sincronizado
CREATE TRIGGER conv_ai AFTER INSERT ON convocatorias BEGIN
    INSERT INTO convocatorias_fts(rowid, descripcion, finalidad, nivel1, nivel2, ai_summary, ai_keywords)
    VALUES (new.id, new.descripcion, new.finalidad, new.nivel1, new.nivel2, new.ai_summary, new.ai_keywords);
END;

CREATE TRIGGER conv_ad AFTER DELETE ON convocatorias BEGIN
    INSERT INTO convocatorias_fts(convocatorias_fts, rowid, descripcion, finalidad, nivel1, nivel2, ai_summary, ai_keywords)
    VALUES('delete', old.id, old.descripcion, old.finalidad, old.nivel1, old.nivel2, old.ai_summary, old.ai_keywords);
END;

CREATE TRIGGER conv_au AFTER UPDATE ON convocatorias BEGIN
    INSERT INTO convocatorias_fts(convocatorias_fts, rowid, descripcion, finalidad, nivel1, nivel2, ai_summary, ai_keywords)
    VALUES('delete', old.id, old.descripcion, old.finalidad, old.nivel1, old.nivel2, old.ai_summary, old.ai_keywords);
    INSERT INTO convocatorias_fts(rowid, descripcion, finalidad, nivel1, nivel2, ai_summary, ai_keywords)
    VALUES (new.id, new.descripcion, new.finalidad, new.nivel1, new.nivel2, new.ai_summary, new.ai_keywords);
END;

-- Metadata de sincronización (reutiliza patrón de beneficiarios_db.py)
CREATE TABLE IF NOT EXISTS sync_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

#### 1.2 Script de sincronización

**Archivo**: `backend/scripts/sync_convocatorias.py`
**Patrón**: Replica `sync_beneficiarios.py` con estas diferencias:

- **Sync inicial**: Recorre por año (2014-2026), paginando con `fechaDesde`/`fechaHasta` por año
- **Sync incremental**: Solo últimos 30 días (`fechaDesde = hoy - 30d`)
- **Detalle**: Para cada convocatoria, opcionalmente fetch el endpoint de detalle (más campos)
  - Fase 1: solo datos del endpoint de búsqueda (rápido, ~2h para 610K)
  - Más adelante: enriquecer con detalle bajo demanda o en background
- **Upsert**: `INSERT OR REPLACE` en vez de DELETE+INSERT (preserva etiquetas IA existentes)
- **Concurrencia**: Semaphore(5) como el actual

```python
# Pseudocódigo del sync incremental
async def sync_recent(days=30):
    fecha_desde = (date.today() - timedelta(days=days)).strftime("%d/%m/%Y")
    fecha_hasta = date.today().strftime("%d/%m/%Y")

    records = await fetch_all_pages(
        endpoint="/convocatorias/busqueda",
        params={"fechaDesde": fecha_desde, "fechaHasta": fecha_hasta}
    )

    upsert_convocatorias(records)  # INSERT OR REPLACE
    rebuild_fts()
    update_sync_metadata("last_sync_convocatorias", datetime.now().isoformat())
```

**Estimaciones de tiempo**:
- Sync inicial completo (610K registros, solo búsqueda): ~2-3 horas
- Sync incremental diario (últimos 30 días, ~5K registros): ~5-10 minutos
- Fetch de detalle para 610K registros: ~8-12 horas adicionales (puede hacerse gradualmente)

#### 1.3 Servicio de base de datos

**Archivo**: `backend/services/convocatorias_db.py`
**Patrón**: Replica `beneficiarios_db.py`

Funciones principales:
- `init_db()` — crea schema (idempotente, llamar en lifespan)
- `has_data()` → bool
- `search_fts(query, page, page_size)` → resultados paginados
- `get_by_bdns_code(code)` → convocatoria completa
- `get_stats()` → conteos por fecha/región/finalidad (para analytics)
- `get_pending_ai_enrichment(limit)` → convocatorias sin procesar por IA

#### 1.4 Ruta híbrida (local + BDNS proxy)

**Archivo**: `backend/routes/convocatorias.py` (modificar existente)

```python
# Lógica de routing (como beneficiarios.py):
# 1. Si hay param `q` (texto libre) → buscar en SQLite FTS5 local
# 2. Si hay filtros estándar (región, fecha, etc.) → proxy a BDNS (datos más frescos)
# 3. Si se pide detalle → primero local, si no existe → BDNS + guardar en local
```

#### 1.5 Cron job

Añadir endpoint admin: `POST /api/admin/sync-convocatorias`
Tarea programada en Coolify: ejecutar diariamente a las 07:00 UTC (tras actualización BDNS ~06:30 CET)

**Archivos a crear/modificar**:
- `backend/services/convocatorias_db.py` (nuevo, ~200 líneas)
- `backend/scripts/sync_convocatorias.py` (nuevo, ~150 líneas)
- `backend/routes/convocatorias.py` (modificar, añadir routing híbrido)
- `backend/routes/admin.py` (añadir endpoint sync-convocatorias)
- `backend/main.py` (init_db para convocatorias en lifespan)

---

### FASE 2: Enriquecimiento con IA (~5 días) — PARCIALMENTE COMPLETADA

**Objetivo**: Cada convocatoria tiene categorías semánticas, resumen ciudadano, keywords y embedding.

> **Nota**: Se implementaron embeddings con OpenAI `text-embedding-3-small` y búsqueda semántica híbrida (FTS5 + coseno). La clasificación con Claude Haiku (categorías IA, resúmenes, keywords) queda pendiente para una fase futura.

#### 2.1 Pipeline de enriquecimiento

**Archivo**: `backend/services/ai_enrichment.py`

```python
# Para cada convocatoria sin procesar:
async def enrich_convocatoria(conv: dict) -> dict:
    """Genera etiquetas IA para una convocatoria."""

    # 1. Construir prompt con datos de la convocatoria
    text = build_prompt(conv)  # descripción + finalidad + organismo + beneficiarios

    # 2. Llamar a Claude API (Haiku para coste, Sonnet para calidad)
    response = await call_claude(
        model="claude-haiku-4-5-20251001",
        system="Eres un experto en subvenciones públicas españolas...",
        prompt=text,
        # Structured output: JSON con categories, summary, target, keywords, difficulty
    )

    # 3. Generar embedding (para búsqueda semántica)
    embedding = await generate_embedding(conv['descripcion'] + ' ' + response['summary'])

    return {
        'ai_categories': response['categories'],      # ["digitalización", "PYME", "innovación"]
        'ai_summary': response['summary'],             # "Ayuda para que pequeñas empresas..."
        'ai_target_audience': response['target'],      # "Autónomos y PYMES < 50 empleados"
        'ai_keywords': response['keywords'],           # "digitalización, software, PYME, kit digital"
        'ai_difficulty': response['difficulty'],        # "media"
        'embedding': embedding,                         # float32 array
    }
```

#### 2.2 Taxonomía de categorías IA

Definir ~30-50 categorías semánticas organizadas jerárquicamente:

```
Emprendimiento y Empresa
├── Creación de empresas
├── Digitalización
├── Internacionalización
├── Innovación y I+D
└── Formación empresarial

Energía y Medio Ambiente
├── Eficiencia energética
├── Energías renovables
├── Economía circular
└── Transición justa

Vivienda y Urbanismo
├── Rehabilitación de vivienda
├── Acceso a vivienda
└── Desarrollo urbano

Educación y Cultura
├── Becas educativas
├── Investigación académica
├── Proyectos culturales
└── Deporte

Empleo y Formación
├── Inserción laboral
├── Formación profesional
├── Economía social
├── Discapacidad e inclusión

Agricultura y Rural
├── Modernización agraria
├── Desarrollo rural
├── Ganadería y pesca
└── PAC y fondos europeos

Social y Sanitario
├── Servicios sociales
├── Sanidad
├── Dependencia
└── Cooperación al desarrollo

Administración Local
├── Infraestructuras municipales
├── Servicios públicos
└── Fondos europeos para AALL
```

#### 2.3 Modelo de embeddings

**Opciones**:

| Modelo | Dimensiones | Coste | Calidad español | Hosting |
|--------|------------|-------|-----------------|---------|
| `text-embedding-3-small` (OpenAI) | 1536 | $0.02/1M tokens | Buena | API |
| `text-embedding-3-large` (OpenAI) | 3072 | $0.13/1M tokens | Muy buena | API |
| `multilingual-e5-small` (HuggingFace) | 384 | $0 | Buena | Local* |
| Claude embeddings (Anthropic) | — | — | — | No disponible aún |

**Recomendación**: `text-embedding-3-small` de OpenAI
- Buen equilibrio coste/calidad
- 610K convocatorias × ~100 tokens/conv = ~61M tokens → **~$1.22 total**
- Incremental: ~100 convocatorias/día × 100 tokens → **<$0.01/día**
- 1536 dims × 4 bytes = 6KB/embedding × 610K = **~3.6GB** de embeddings
- Alternativa: reducir a 512 dims con `dimensions` param → **~1.2GB**

\* Local requiere ~500MB RAM extra para el modelo, viable en el servidor Hetzner (8 GB).

#### 2.4 Costes de IA detallados

**Procesamiento batch inicial (610K convocatorias)**:

| Componente | Modelo | Tokens est. | Coste |
|-----------|--------|-------------|-------|
| Clasificación + resumen | Claude Haiku 4.5 | ~300M input, ~150M output | ~$4.50 in + ~$15 out = **~$20** |
| Embeddings | text-embedding-3-small | ~61M tokens | **~$1.22** |
| **Total inicial** | | | **~$21** |

**Coste incremental diario (~100 nuevas convocatorias)**:

| Componente | Coste/día |
|-----------|-----------|
| Clasificación + resumen | ~$0.003 |
| Embeddings | ~$0.0002 |
| **Total/día** | **<$0.01** |
| **Total/mes** | **~$0.10** |

#### 2.5 Búsqueda semántica

**Archivo**: `backend/services/semantic_search.py`

```python
# Opción A: En memoria (si caben los embeddings en RAM)
# 610K × 512 dims × 4 bytes = 1.2GB — demasiado para un servidor pequeño
# Con 50K convocatorias abiertas/recientes: ~100MB — factible

# Opción B: sqlite-vec extension
# SELECT * FROM convocatorias
# WHERE embedding MATCH ?
# ORDER BY distance LIMIT 20

# Opción C: Hybrid scoring (recomendado)
async def search_semantic(query: str, k: int = 20) -> list:
    # 1. FTS5 keyword search (rápido, filtro grueso)
    fts_results = search_fts(query, limit=200)

    # 2. Generar embedding del query
    query_embedding = await generate_embedding(query)

    # 3. Re-rank por similitud coseno sobre los 200 candidatos FTS
    ranked = rerank_by_similarity(fts_results, query_embedding)

    return ranked[:k]
```

**Recomendación**: Opción C (hybrid) — combina velocidad de FTS con relevancia semántica, y no requiere tener todos los embeddings en RAM.

#### 2.6 Script de enriquecimiento

**Archivo**: `backend/scripts/enrich_convocatorias.py`

```python
# Ejecutar como cron job tras sync_convocatorias
# 1. Obtener convocatorias sin ai_processed_at
# 2. Para cada batch de 50:
#    a. Generar clasificación + resumen con Claude Haiku
#    b. Generar embedding con OpenAI
#    c. Actualizar SQLite
# 3. Reconstruir FTS5 (para incluir ai_summary y ai_keywords)
```

**Archivos a crear**:
- `backend/services/ai_enrichment.py` (nuevo, ~200 líneas)
- `backend/services/semantic_search.py` (nuevo, ~100 líneas)
- `backend/scripts/enrich_convocatorias.py` (nuevo, ~120 líneas)
- `backend/config.py` (añadir ANTHROPIC_API_KEY, OPENAI_API_KEY)

---

### FASE 3: Analytics Dashboard (~2 días) — COMPLETADA

**Objetivo**: Página `/datos` con estadísticas sobre las convocatorias replicadas.

#### 3.1 Endpoints de analytics

**Archivo**: `backend/routes/analytics.py` (nuevo)

```python
# GET /api/analytics/summary
# → total convocatorias, total presupuesto, convocatorias abiertas, por región top-10

# GET /api/analytics/trends?periodo=mensual&desde=2024-01
# → serie temporal de convocatorias publicadas y presupuesto

# GET /api/analytics/by-category
# → distribución por categoría IA (treemap data)

# GET /api/analytics/by-region
# → distribución geográfica (mapa data)

# GET /api/analytics/by-organism
# → top organismos por número de convocatorias y presupuesto
```

#### 3.2 Frontend

**Archivo**: `frontend/src/pages/analytics.js` (nuevo)

- Gráficos con Chart.js o similar (ligero, sin framework)
- Tendencias temporales (línea)
- Distribución por categoría IA (treemap/barras)
- Top organismos (barras horizontales)
- Mapa de calor por región (mapa de España)

---

### FASE 4: Alertas sin registro (~3-4 días)

**Objetivo**: Los usuarios pueden suscribirse a alertas por email sin crear cuenta. Zero auth, mínimo RGPD.

#### 4.1 Modelo: email-only alerts (sin cuentas de usuario)

```sql
-- Añadir a convocatorias.db (o alertas.db separado)
CREATE TABLE alert_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    email_hash TEXT NOT NULL,           -- SHA256 para deduplicación
    filters_json TEXT NOT NULL,          -- {"region": "...", "finalidad": "...", "q": "..."}
    frequency TEXT DEFAULT 'daily',      -- 'daily' | 'weekly'
    verified INTEGER DEFAULT 0,          -- 1 tras confirmar email
    verify_token TEXT,                   -- token de verificación
    unsubscribe_token TEXT NOT NULL,     -- token para darse de baja
    last_checked TEXT,                   -- última vez que se comprobaron novedades
    last_sent TEXT,                      -- última vez que se envió email
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_alerts_active ON alert_subscriptions(active, verified);
CREATE INDEX idx_alerts_email ON alert_subscriptions(email_hash);
```

#### 4.2 Flujo de usuario

```
1. Usuario busca ayudas en Hola Ayudas con filtros
2. Ve botón "Recibir alertas de esta búsqueda por email"
3. Introduce su email → POST /api/alertas
4. Recibe email de verificación (enlace con token)
5. Hace clic → GET /api/alertas/verificar?token=xxx
6. Desde ese momento, recibe digest diario/semanal con nuevas ayudas que coincidan
7. Cada email tiene enlace "Darme de baja" → GET /api/alertas/baja?token=xxx
```

#### 4.3 Con IA (alertas semánticas)

Si el usuario escribe texto libre en vez de (o además de) filtros:
- "Ayudas para rehabilitar mi casa en Andalucía"
- Se guarda como `filters_json: {"q_semantic": "rehabilitar casa", "region": "andalucia"}`
- El cron job usa búsqueda semántica (embedding similarity) en vez de solo keyword match
- El email incluye resumen IA de cada ayuda nueva

#### 4.4 Servicio de email

**Archivo**: `backend/services/email_service.py`

**Recomendación**: Resend (https://resend.com)
- Free tier: 100 emails/día, 3000/mes
- API simple, buena documentación
- SDK Python: `resend`
- Alternativa: SendGrid free tier (100 emails/día)

```python
import resend

async def send_alert_digest(email: str, new_grants: list[dict], unsubscribe_token: str):
    html = render_digest_template(new_grants, unsubscribe_token)
    resend.Emails.send({
        "from": "alertas@holaayudas.com",
        "to": email,
        "subject": f"{len(new_grants)} nuevas ayudas que te interesan",
        "html": html,
    })
```

#### 4.5 Cron job de alertas

```python
# POST /api/admin/send-alerts (protegido con ADMIN_SECRET)
# Tarea programada en Coolify: diario a las 08:00 UTC

async def check_and_send_alerts():
    subscriptions = get_active_verified_subscriptions()

    for sub in subscriptions:
        filters = json.loads(sub['filters_json'])

        # Buscar convocatorias nuevas desde last_checked
        if 'q_semantic' in filters:
            new_grants = await search_semantic(filters['q_semantic'], since=sub['last_checked'])
        else:
            new_grants = await search_local(filters, since=sub['last_checked'])

        if new_grants:
            await send_alert_digest(sub['email'], new_grants, sub['unsubscribe_token'])
            update_last_sent(sub['id'])

        update_last_checked(sub['id'])
```

#### 4.6 RGPD mínimo

Sin cuentas de usuario, el impacto RGPD es mínimo:
- Solo almacenamos email + filtros de búsqueda
- Email hasheado para deduplicación
- Consentimiento explícito (double opt-in via email verification)
- Derecho de supresión: enlace de baja en cada email
- No compartimos datos con terceros
- Añadir texto legal mínimo en el formulario de suscripción

**Archivos a crear/modificar**:
- `backend/services/email_service.py` (nuevo, ~80 líneas)
- `backend/services/alerts_service.py` (nuevo, ~150 líneas)
- `backend/routes/alerts.py` (nuevo, ~100 líneas)
- `backend/scripts/send_alerts.py` (nuevo, ~50 líneas)
- `backend/routes/admin.py` (añadir endpoint send-alerts)
- `frontend/src/components/AlertSubscribe.js` (nuevo, formulario)
- `frontend/src/pages/search.js` (añadir botón de alertas)

---

### FASE 5 (futuro): RSS Feeds (~1 día extra)

Complemento a las alertas email para usuarios técnicos:

```python
# GET /api/rss?region=15&finalidad=3&q=digitalización
# → XML Atom/RSS feed con las últimas convocatorias que coinciden

@router.get("/rss", response_class=Response)
async def rss_feed(region: str = None, finalidad: str = None, q: str = None):
    grants = search_local(filters, limit=50, order_by="fecha_recepcion DESC")
    xml = render_rss_xml(grants, filters)
    return Response(content=xml, media_type="application/rss+xml")
```

- Zero gestión de usuarios
- El usuario pone la URL en su lector RSS
- Se puede cachear 30min en memoria

---

### FASE 6 (futuro): Réplica de Concesiones

Solo si la Fase 1-4 tiene tracción. Añade:
- 16.1M registros, ~3GB SQLite
- Cruce convocatoria ↔ concesión (tasa de ejecución)
- Todos los beneficiarios individuales (no solo top)
- Analytics de gasto real (no solo presupuestado)

**Decisión**: postergar hasta validar el valor de las fases anteriores.

---

## Resumen de costes

### Desarrollo (one-time)

| Fase | Esfuerzo | Qué incluye |
|------|----------|-------------|
| Fase 1: Réplica convocatorias | ~3 días | Schema, sync script, servicio DB, ruta híbrida |
| Fase 2: IA enrichment | ~5 días | Pipeline IA, embeddings, búsqueda semántica |
| Fase 3: Analytics dashboard | ~2 días | Endpoints + página frontend con gráficos |
| Fase 4: Alertas email | ~3-4 días | Suscripciones, verificación, digest, cron |
| **TOTAL** | **~13-14 días** | Incremental, con valor desde la Fase 1 |

### Operativo mensual

| Concepto | Coste/mes |
|----------|-----------|
| Servidor Hetzner con Coolify (ya existente) | Coste fijo del servidor |
| Procesamiento IA incremental | ~$0.10 |
| Resend free tier (emails) | $0 |
| **Total** | **~$0.10/mes** además del servidor |

### Costes one-time IA

| Concepto | Coste |
|----------|-------|
| Batch inicial: clasificación 610K convocatorias | ~$20 |
| Batch inicial: embeddings 610K convocatorias | ~$1.22 |
| **Total** | **~$21** |

---

## Dependencias nuevas

```toml
# pyproject.toml
[project]
dependencies = [
    # ... existentes ...
    "anthropic>=0.40.0",          # Claude API para clasificación
    "openai>=1.50.0",             # Embeddings
    "resend>=2.0.0",              # Email service
    "numpy>=2.0.0",               # Operaciones vectoriales (coseno similarity)
]
```

No se necesita PostgreSQL, Redis ni Celery. SQLite + tareas programadas de Coolify es suficiente para el volumen esperado (<1000 suscriptores).

---

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| BDNS bloquea scraping agresivo | Media | Alto | Semáforo de concurrencia (ya implementado), backoff exponencial, sync en horario bajo |
| Calidad de clasificación IA baja | Baja | Medio | Validar manualmente muestra de 100 convocatorias antes de batch completo; iterar prompt |
| Embeddings no capturan bien español administrativo | Media | Medio | Hybrid search (FTS + semántica); probar modelos multilingües |
| Volumen de datos se pierde en redeploy | Baja | Alto | El volumen `/app/data` de Coolify es persistente; backup periódico a S3/R2 |
| Coste IA escala si hay muchas más convocatorias | Baja | Bajo | El crecimiento es ~50-100/día, coste marginal <$0.01/día |
| RGPD con emails de alertas | Baja | Medio | Double opt-in, enlace de baja, texto legal, no compartir datos |

---

## Orden de implementación recomendado

```
Semana 1:  Fase 1 (réplica convocatorias) → valor inmediato: FTS local, independencia de BDNS
Semana 2:  Fase 2 (IA enrichment) → killer feature: búsqueda semántica, resúmenes
Semana 3:  Fase 3 (analytics) + Fase 4 (alertas) → engagement y retención
```

Cada fase es autónoma y entrega valor por sí sola. Si después de la Fase 1 decides que no merece continuar, tienes una base de datos útil con FTS5.
