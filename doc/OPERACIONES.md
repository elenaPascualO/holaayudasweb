# Manual de operaciones — Hola Ayudas

Guía de referencia para mantener la app en producción (Coolify): despliegue, variables de entorno, sincronizaciones, búsqueda semántica, OpenAI y resolución de problemas.

---

## 1. Visión general

```
Usuario ──> Frontend (Vite, servido por FastAPI) ──> Backend FastAPI ──┬──> SQLite local (/app/data)
                                                                       ├──> API BDNS (infosubvenciones.es)
                                                                       └──> OpenAI (embeddings + posts)
```

- **Un solo contenedor** (`Dockerfile` multi-stage): el frontend se compila con Bun y lo sirve FastAPI en el puerto **8000**.
- **Datos persistentes** en `/app/data` (volumen persistente en Coolify):
  - `convocatorias.db` — réplica local de convocatorias BDNS (~659K), índice FTS5, embeddings (`conv_embeddings`) y posts generados.
  - `beneficiarios.db` — ranking de beneficiarios por año.
- **Índice FAISS**: vive en memoria para las búsquedas y **se guarda en disco** en `/app/data/faiss.index` (+ `faiss.index.meta.json`). SQLite es la fuente de verdad; el archivo es una caché. Tipo `OPQ64,IVF1024,PQ64`.
  - **Arranque**: lee el archivo (segundos) y añade los embeddings de SQLite que falten. Solo si no hay archivo, o es incompatible (otro modelo/dimensiones) o está corrupto, hace una **construcción completa**.
  - **Tras `daily` / `backfill-embeddings`**: añade solo los vectores nuevos (sin reentrenar) y guarda. Milisegundos/segundos.
  - **Construcción completa / reentrenamiento** (`POST /api/admin/faiss/rebuild`): tarda **más de 12 minutos** y llega a **~5 GB de RSS** (medido en oct 2026, servidor de 8 GB). El índice anterior sigue sirviendo búsquedas mientras tanto.
  - Todas las operaciones de escritura del índice van tras **un único bloqueo**: nunca puede haber dos construcciones a la vez (no cabrían en memoria).

### Qué depende de qué

| Funcionalidad | Fuente | Si falla… |
|---|---|---|
| Búsqueda principal (`/api/convocatorias`) | SQLite local | No depende de OpenAI |
| Búsqueda semántica (`/api/search`) | FTS5 + FAISS + OpenAI (embedding de la consulta) | Sin OpenAI → degrada **en silencio** a solo palabras clave |
| Detalle de ayuda, catálogos, concesiones | API BDNS (con caché) | Errores al usuario si BDNS cae |
| Sync diario | API BDNS + OpenAI | Sin OpenAI → termina OK pero sin embeddings nuevos (solo log) |
| Generación de posts | OpenAI (`POSTS_OPENAI_MODEL`) | Falla la tarea |
| Feedback | Discord webhook | Se guarda pero no notifica |
| Alertas de fallo de sync | SMTP | No llegan emails |

---

## 2. Variables de entorno (Coolify → Environment Variables)

Tras cambiar cualquier variable hay que hacer **Redeploy** (el contenedor solo las lee al arrancar).

| Variable | Obligatoria | Default | Para qué |
|---|---|---|---|
| `ENVIRONMENT` | Sí | `development` | Poner `production` (activa HSTS, redirección a www, oculta `/docs`) |
| `ALLOWED_ORIGINS` | Sí (prod) | — | Orígenes CORS, separados por comas |
| `SITE_BASE_URL` | No | `https://www.holaayudas.com` | URLs canónicas, sitemap y redirección www |
| `ADMIN_SECRET` | Sí | — | Token Bearer de los endpoints `/api/admin/*` |
| `OPENAI_API_KEY` | Sí | — | Embeddings y posts. Debe ser una **project key** (`sk-proj-…`) |
| `POSTS_OPENAI_MODEL` | No | `gpt-4o` | Modelo para posts (`gpt-4o-mini` es más barato) |
| `CONVOCATORIAS_DB_PATH` | No | `/app/data/convocatorias.db` | Ruta de la BD de convocatorias |
| `FAISS_INDEX_PATH` | No | `faiss.index` junto a la BD de convocatorias | Índice FAISS guardado en disco. Debe estar en el volumen persistente |
| `SITEMAPS_DIR` | No | `sitemaps/` junto a la BD de convocatorias | Sitemaps pregenerados (`.xml.gz`). Debe estar en el volumen persistente |
| `BENEFICIARIOS_DB_PATH` | No | `/app/data/beneficiarios.db` | Ruta de la BD de beneficiarios |
| `DISCORD_WEBHOOK_URL` | No | — | Notificaciones de feedback |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `ALERT_EMAIL_TO` | No | `SMTP_PORT=587` | Emails de alerta cuando falla un sync (hacen falta **todas**) |
| `BDNS_BASE_URL`, `BDNS_TIMEOUT` | No | API oficial, `30` | API upstream |
| `CACHE_TTL_CATALOGS` / `_SEARCH` / `_DETAIL` | No | `86400` / `300` / `3600` | TTL de caché (segundos) |

---

## 3. Despliegue

1. Push a `master` → Coolify construye la imagen con el `Dockerfile` y despliega (o **Redeploy** manual).
2. Al arrancar: se inicializan las BDs, se carga la plantilla SEO y **FAISS se carga desde disco en segundo plano** (segundos). Si no existe `/app/data/faiss.index`, se construye desde cero (más de 12 min, ~5 GB) y se guarda.
3. Comprobar tras el deploy:
   - La web carga y la búsqueda funciona.
   - `GET /api/admin/faiss/status` → `"ready": true`, `"on_disk": true` (ver §5).
   - En los logs: `FAISS index loaded from disk: N vectors` y ningún `FAISS index load failed`.

**Importante:** un redeploy/reinicio **cancela cualquier sync en marcha** y borra el estado en memoria (`/status` vuelve a `idle`). Los syncs se pueden relanzar sin problema: solo procesan lo pendiente.

Si FAISS se está construyendo (`"building": true`), puedes lanzar syncs: la actualización del índice esperará a que termine la construcción y no se lanzará una segunda.

---

## 4. Acceso a la terminal del contenedor

Coolify → aplicación → **Terminal**. La shell es `sh` (dash), no bash:

- ❌ `${VAR:0:8}` → `Bad substitution`
- ✅ `printf '%s\n' "$VAR" | cut -c1-8`

`ADMIN_SECRET` y `OPENAI_API_KEY` ya están en el entorno, así que los comandos de este manual los usan directamente. Dentro del contenedor la API está en `http://localhost:8000`.

Desde fuera (tu ordenador), sustituye `http://localhost:8000` por `https://www.holaayudas.com` y `$ADMIN_SECRET` por el valor real.

> Los endpoints que lanzan tareas (`POST /sync/*`, `/posts/*`) tienen rate limit de **10 peticiones/minuto por IP**.

---

## 5. Endpoints de administración

Todos requieren la cabecera `Authorization: Bearer $ADMIN_SECRET`.

| Método | Ruta | Uso |
|---|---|---|
| POST | `/api/admin/sync/convocatorias?mode=<modo>` | Lanza sync de convocatorias en segundo plano |
| GET | `/api/admin/sync/convocatorias/status` | Estado del sync actual/último (`idle`, `running`, `completed`, `failed`, `cancelled`) |
| GET | `/api/admin/sync/convocatorias/stats` | Contadores: total, con detalle, con embedding, pendientes |
| POST | `/api/admin/sync/beneficiarios` | Lanza sync de beneficiarios |
| GET | `/api/admin/sync/beneficiarios/status` | Estado del sync de beneficiarios |
| GET | `/api/admin/sync/beneficiarios/stats` | Totales por año |
| GET | `/api/admin/faiss/status` | `ready`, `total_vectors`, `index_type`, `building`, `built_at`, `on_disk` |
| POST | `/api/admin/sitemaps/regenerate` | Regenera todos los sitemaps en segundo plano (normalmente no hace falta, ver §6) |
| GET | `/api/admin/sitemaps/status` | `generating`, `generated_at`, `files`, `urls`, `elapsed_seconds` |
| POST | `/api/admin/faiss/rebuild` | Reentrena el índice desde cero y lo guarda (ocasional, ver §6) |
| POST | `/api/admin/posts/generate?post_type=<tipo>` | Genera un post con OpenAI |
| GET | `/api/admin/posts/generate/status` | Estado de la generación |
| GET | `/api/admin/posts?status=&post_type=&limit=` | Lista posts |
| PATCH / DELETE | `/api/admin/posts/{id}` | Cambiar estado (`published`/`discarded`) o borrar |

Atajo para no repetir la cabecera:

```sh
AUTH="Authorization: Bearer $ADMIN_SECRET"
API=http://localhost:8000/api/admin
curl -s -H "$AUTH" $API/sync/convocatorias/stats
```

---

## 6. Sincronización de convocatorias

### Modos

| Modo | Qué hace | Límite por ejecución | Usa OpenAI |
|---|---|---|---|
| `daily` | Descarga las últimas páginas de BDNS (hasta 10, para en cuanto no hay nuevas) + detalle de pendientes + embeddings de pendientes | 1.000 detalles, 1.000 embeddings | Sí |
| `full-list` | Carga histórica completa del listado (~659K) | — | No |
| `backfill-detail` | Descarga el detalle de convocatorias que no lo tienen | 30.000 | No |
| `backfill-embeddings` | Genera embeddings de convocatorias **con detalle** y sin embedding | 50.000 (lotes de 500) | Sí |

Notas:
- Sin detalle no hay embedding → el orden siempre es **detalle → embeddings**.
- `backfill-embeddings` se **salta** si el último `backfill-detail` (desde el último reinicio) falló.
- Al terminar `daily` o `backfill-embeddings`, los vectores nuevos **se añaden solos** al índice FAISS y se guarda en disco (sin reentrenar). Ojo: `/status` marca `completed` justo *antes* de esa actualización.
- Si un sync falla con excepción, se envía un email de alerta (si SMTP está configurado). **Los fallos de OpenAI dentro de un lote de embeddings no lanzan excepción**: se registran en el log y el sync termina como `completed`.
- Referencia de tiempos: ~28K embeddings tardan ~100 s. El backfill de detalle es mucho más lento (llamadas a BDNS una a una, concurrencia 3).

### Tareas programadas

El sync diario debe estar programado (Coolify → **Scheduled Tasks**, o un cron externo). Recomendado:

| Frecuencia | Comando |
|---|---|
| Diario, 07:00 UTC (tras la actualización de BDNS) | `curl -s -X POST "http://localhost:8000/api/admin/sync/convocatorias?mode=daily" -H "Authorization: Bearer $ADMIN_SECRET"` |
| Semanal/mensual | `curl -s -X POST "http://localhost:8000/api/admin/sync/beneficiarios" -H "Authorization: Bearer $ADMIN_SECRET"` |

> Verifica en Coolify qué tareas están realmente configuradas: no están definidas en el repo.

### Sitemaps

Los sitemaps (`/sitemap.xml` y los que lista) se **pregeneran** en `/app/data/sitemaps/` y se sirven desde disco en milisegundos. Generarlos lee ~600K filas y tarda; por eso nunca se hace dentro de una petición en el event loop.

- Se regeneran **al arrancar** si faltan o tienen más de 24 h, y **después de cada `daily`** completado. Mientras se regeneran se siguen sirviendo los anteriores.
- Si un archivo aún no existe (primer arranque), la ruta lo genera bajo demanda en un hilo, sin bloquear el resto de peticiones.
- Regenerar a mano: `curl -s -X POST -H "Authorization: Bearer $ADMIN_SECRET" http://localhost:8000/api/admin/sitemaps/regenerate`.
- Comprobar: `GET /api/admin/sitemaps/status` y `ls -la /app/data/sitemaps/`. Desde fuera: `curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" -H "Accept-Encoding: gzip" https://www.holaayudas.com/sitemap.xml` → `200` en menos de 1 s.
- Seguimiento en Google Search Console → Sitemaps (estado "Correcto").
- Las consultas de los sitemaps se resuelven solo con índices (`idx_conv_sitemap_cover`, `idx_conv_sitemap_fin_cover`), contando con que **no hay estadísticas del planificador**. **No ejecutes `ANALYZE` en la BD** sin revisar antes los planes (ver `doc/tasks/sitemap-covering-index.md`).

### Reentrenar FAISS (cada pocos meses)

Los syncs añaden vectores a un índice ya entrenado. Con el tiempo, si cambia mucho el tipo de convocatorias, conviene reentrenarlo (no urge: cientos de altas al día sobre ~659K). Lánzalo a mano en un momento tranquilo, **no a la vez que otros procesos pesados**:

```sh
curl -s -X POST -H "Authorization: Bearer $ADMIN_SECRET" http://localhost:8000/api/admin/faiss/rebuild
```

- `{"status":"started"}` → en marcha (más de 12 min, ~5 GB de RAM). El índice actual sigue funcionando hasta que el nuevo lo sustituye.
- `{"status":"skipped"}` → ya hay una construcción o actualización en curso.
- Progreso: `faiss/status` (`building: true` → `false`, `built_at` cambia) y los logs (`Pass 1/2`, `Pass 2/2`, `FAISS rebuild completed`).
- Si falla, se envía email de alerta (si SMTP está configurado).

También puedes forzar una reconstrucción completa en el próximo arranque borrando el archivo: `rm /app/data/faiss.index /app/data/faiss.index.meta.json`.

---

## 7. Procedimiento: poner al día detalle y embeddings (backfill completo)

Úsalo tras una caída de OpenAI, un cambio de key, o si `stats` muestra pendientes.

**0. Comprobar que no hay nada corriendo y ver qué falta**

```sh
curl -s -H "Authorization: Bearer $ADMIN_SECRET" http://localhost:8000/api/admin/sync/convocatorias/status
curl -s -H "Authorization: Bearer $ADMIN_SECRET" http://localhost:8000/api/admin/sync/convocatorias/stats
```

- `status` debe ser `idle`, `completed` o `failed` (no `running`).
- `GET /api/admin/faiss/status` debe dar `"ready": true`. Si no, FAISS se está construyendo: **espera** antes de lanzar nada (ver §3).
- En `stats` mira `pending_detail` y `pending_embedding`.

**1. Backfill de detalle** (solo si `pending_detail` es significativo; unas pocas sin detalle es normal)

```sh
curl -s -X POST -H "Authorization: Bearer $ADMIN_SECRET" \
  "http://localhost:8000/api/admin/sync/convocatorias?mode=backfill-detail"
```

Seguir con `/status` hasta `completed`. Repetir mientras `pending_detail` siga bajando.

**2. Backfill de embeddings**

```sh
curl -s -X POST -H "Authorization: Bearer $ADMIN_SECRET" \
  "http://localhost:8000/api/admin/sync/convocatorias?mode=backfill-embeddings"
```

- Respuesta esperada: `{"status":"started","mode":"backfill-embeddings"}`.
- Progreso en `/status` (`embeddings_generated` / `embedding_total`) o en logs (`Embedding batch: X/Y generated`).
- Repetir hasta que `pending_embedding` sea 0.
- Si aparece `Embedding batch failed` en los logs → ver §9.

**3. Comprobaciones finales**

a) Cobertura:
```sh
curl -s -H "Authorization: Bearer $ADMIN_SECRET" http://localhost:8000/api/admin/sync/convocatorias/stats
```
→ `pending_embedding: 0`.

b) FAISS actualizado (unos segundos tras `completed`):
```sh
curl -s -H "Authorization: Bearer $ADMIN_SECRET" http://localhost:8000/api/admin/faiss/status
```
→ `"ready": true`, `"on_disk": true` y `total_vectors` = `with_embedding`. En logs: `Added N new vectors to FAISS index` + `FAISS index saved to …`, y ningún `Failed to update FAISS index`.

c) Búsqueda semántica de extremo a extremo:
```sh
curl -s "http://localhost:8000/api/search?q=ayudas%20para%20j%C3%B3venes%20que%20quieren%20montar%20un%20negocio&topK=5" | head -c 1500
```
→ resultados relevantes y **ningún** `Failed to embed query` en los logs.

d) Coste en https://platform.openai.com/usage.

**Alternativa sin API** (consulta directa a SQLite; la imagen no trae el cliente `sqlite3`):

```sh
python3 -c "
import os, sqlite3
db = os.environ.get('CONVOCATORIAS_DB_PATH', '/app/data/convocatorias.db')
c = sqlite3.connect(db)
t, d, e = c.execute('''SELECT COUNT(*), SUM(c.detail_fetched=1), SUM(e.convocatoria_id IS NOT NULL)
  FROM convocatorias c LEFT JOIN conv_embeddings e ON e.convocatoria_id=c.id''').fetchone()
print(f'total={t}  con_detalle={d}  con_embedding={e}')
print(f'faltan_detalle={t-d}  faltan_embedding={d-e}')
"
```

---

## 8. OpenAI

### Dónde se usa

| Uso | Código | Modelo | Cuándo |
|---|---|---|---|
| Embedding de la consulta | `backend/services/semantic_search.py` (`_embed_query`) | `text-embedding-3-small` | Cada `GET /api/search` con texto (si FAISS está listo) |
| Embeddings de convocatorias | `backend/scripts/sync_convocatorias.py` (`sync_backfill_embeddings`) | `text-embedding-3-small` | `daily` y `backfill-embeddings` |
| Posts para redes | `backend/scripts/generate_posts.py` | `POSTS_OPENAI_MODEL` | `POST /api/admin/posts/generate` |

### Comprobar que la key funciona

Desde la terminal del contenedor:

```sh
printf '%s\n' "$OPENAI_API_KEY" | cut -c1-8      # debe salir sk-proj-

curl -s https://api.openai.com/v1/embeddings \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"text-embedding-3-small","input":"test"}' | head -c 300
```

| Respuesta | Significado | Acción |
|---|---|---|
| `{"object":"list","data":[{"object":"embedding",…` | OK | — |
| `billing_not_active` | Cuenta sin método de pago / créditos | Recargar en Billing (§8.1) |
| `insufficient_quota` | Créditos agotados o límite de gasto alcanzado | Recargar o subir el límite |
| `invalid_api_key` | Key revocada/incorrecta | Crear nueva key (§8.2) |
| Variable vacía | No configurada en Coolify | Añadirla y redeploy |

### 8.1 Recargar créditos

1. https://platform.openai.com/settings/organization/billing con la organización **Personal** seleccionada.
2. Añadir método de pago / comprar créditos.
3. Recomendado: en *Limits*, fijar un límite de gasto mensual; opcionalmente activar recarga automática para que no se vuelva a quedar sin saldo.
4. La activación puede tardar unos minutos en propagarse. Repetir el `curl` de prueba.

### 8.2 Rotar la API key

1. https://platform.openai.com/api-keys (organización **Personal**) → *Create new secret key* → proyecto (p. ej. *Default project*). Copiarla (solo se muestra una vez).
2. Coolify → Environment Variables → sustituir `OPENAI_API_KEY` → **Redeploy** (esperar antes a que termine cualquier sync).
3. Verificar con los comandos de arriba (`sk-proj-` + `curl`).
4. Actualizar también el `.env` local si se usa.
5. Revocar la key antigua (*Settings → Organization → API keys*).

> OpenAI está desactivando las **legacy user API keys** (`sk-…` sin `proj`) sin uso en 14 días. Usa siempre project keys.

### 8.3 Recuperar acceso a la cuenta

Si no sabes con qué email está la cuenta: mira el destinatario de los correos de OpenAI (avisos, recibos de Stripe), prueba *Continue with Google/Microsoft/Apple* en el login, o "Forgot password" con cada email candidato. Último recurso: https://help.openai.com con el ID de organización.

---

## 9. Resolución de problemas

### Qué buscar en los logs de Coolify

| Mensaje | Significado |
|---|---|
| `Failed to embed query: …` | OpenAI falló en una búsqueda → la búsqueda va solo por palabras clave. El error de OpenAI va detrás (p. ej. `billing_not_active`) |
| `Embedding batch failed: …` | OpenAI falló en un sync → se para el backfill; lo procesado se conserva |
| `OPENAI_API_KEY not configured` | Falta la variable |
| `No convocatorias need embedding backfill` | Nada pendiente (no se llamó a OpenAI) |
| `Embedding batch: X/Y generated` | Backfill avanzando correctamente |
| `Embedding backfill complete: N generated` | Fin del backfill |
| `FAISS index loaded from disk: N vectors` | Arranque rápido desde el archivo (lo normal) |
| `No saved FAISS index` / `… incompatible …` / `Could not read saved FAISS index` | Se va a hacer una construcción completa (~12 min, ~5 GB) |
| `Building FAISS index…`, `Pass 1/2`, `Pass 2/2`, `added N / M vectors` | Construcción completa en curso |
| `FAISS index ready: N vectors indexed` | Construcción completa terminada |
| `Updating FAISS index after … sync` → `Added N new vectors…` / `already up to date` | Actualización incremental tras un sync |
| `FAISS index saved to …` | Índice guardado en disco |
| `Generating sitemaps in …` → `Sitemaps generated: N files, M URLs in S s` | Generación de sitemaps (arranque, tras `daily` o manual) |
| `Sitemaps are up to date — not regenerating` | Arranque con sitemaps de menos de 24 h |
| `Creating index idx_conv_sitemap_… (one-off, may take minutes)` → `Created index … in S s` | Primer arranque tras añadir los índices de sitemaps. **Mientras se crean, las escrituras en la BD esperan** (no lanzar syncs) |
| `Sitemap index creation failed` | No se pudieron crear los índices; los sitemaps se generan igual, más lento |
| `Sitemap … not pregenerated — building on demand` | Se pidió un sitemap que aún no existe en disco (normal solo en el primer arranque) |
| `Sitemap generation failed` | Falló la generación; se siguen sirviendo los archivos anteriores (email de alerta si SMTP está configurado) |
| `Failed to update FAISS index` / `FAISS index load failed` / `FAISS rebuild failed` | FAISS no se ha cargado/actualizado → revisar el error (búsqueda solo FTS si no está listo) |
| `Skipping backfill-embeddings: last backfill-detail failed` | Relanzar `backfill-detail` hasta que termine bien |
| `Background sync failed` | Excepción en el sync (se envía email si SMTP está configurado) |
| `ADMIN_SECRET is not set` / `Invalid admin token` | Problema con el token de admin |

### Problemas típicos

**La búsqueda semántica no encuentra cosas que debería**
1. `faiss/status` → ¿`ready: true`? Si no, revisar logs de carga y memoria del contenedor.
2. Logs → ¿`Failed to embed query`? → comprobar key (§8).
3. `stats` → ¿`pending_embedding` alto? → backfill (§7).

**Las convocatorias nuevas no aparecen**
1. ¿Está programado el sync `daily` (§6)? ¿Último resultado en `/status`?
2. ¿Llegó algún email de fallo?
3. Lanzar `daily` a mano y revisar logs.

**`/status` dice `idle` aunque se lanzó un sync**
El contenedor se reinició (deploy, OOM…). El estado es en memoria. Relanzar.

**El contenedor se reinicia solo**
Revisar memoria en Coolify. La construcción completa de FAISS es el punto de mayor consumo (~5 GB): ocurre en el primer arranque sin `faiss.index`, si el archivo es incompatible o corrupto, o al llamar a `POST /faiss/rebuild`. Si el contenedor se reinicia en bucle construyendo FAISS, mira si el archivo se está guardando (`ls -la /app/data/faiss.index*`).

Diagnóstico desde la terminal del contenedor:
```sh
head -3 /proc/meminfo                                         # RAM del servidor
cat /sys/fs/cgroup/memory.max /sys/fs/cgroup/memory.current   # límite y uso del contenedor
grep oom /sys/fs/cgroup/memory.events                         # muertes por OOM (se reinicia con el contenedor)
```

---

## 10. Checklist periódico (mensual)

- [ ] `stats`: `pending_detail` y `pending_embedding` cerca de 0.
- [ ] `faiss/status`: `ready: true`, `total_vectors` ≈ `with_embedding`.
- [ ] Logs: sin `Failed to embed query` ni `Embedding batch failed`.
- [ ] Saldo y consumo en https://platform.openai.com/usage.
- [ ] Último `daily` en `/status` → `completed` con fecha reciente.
- [ ] Probar una búsqueda en la web.

---

## 11. Desarrollo local

```bash
uv sync                                                  # backend
cd frontend && bun install                               # frontend

uv run uvicorn backend.main:app --reload --port 8001     # terminal 1 (Vite hace proxy de /api a :8001)
cd frontend && bun run dev                               # terminal 2

uv run pytest -v                                         # tests backend
cd frontend && bun run test:run                          # tests frontend

uv run python -m backend.scripts.sync_convocatorias daily   # sync manual en local
```

Las variables se leen de `.env` en la raíz del proyecto (no se sube al repo).
