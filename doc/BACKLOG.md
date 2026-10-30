# Backlog

Ideas y problemas detectados que **todavía no tienen spec**. Para trabajar en uno: escribir su spec en `doc/tasks/<nombre>.md` siguiendo el flujo de `AGENTS.md` (spec → tests → código → suite completa en verde) y quitarlo de aquí cuando la spec exista.

Prioridad orientativa: **Alta** (afecta a usuarios, SEO o disponibilidad), **Media** (riesgo operativo o coste), **Baja** (mejora o limpieza).

---

## Specs candidatas

### Ayudas "abiertas" que quizá no lo están — Alta

- **Problema:** el criterio de "abierta" es `fecha_fin_solicitud IS NULL OR fecha_fin_solicitud >= hoy`. El sitemap de abiertas tiene 6 páginas (~250–300K ayudas), una cifra muy alta frente a las ~659K totales. Probablemente muchas no tienen fecha de fin en la BDNS y cuentan como abiertas aunque estén cerradas.
- **Impacto:** Google recibe esas URLs con prioridad alta (0.8, `weekly`), y puede que los filtros o contadores de "abiertas" de la web también estén inflados.
- **Primer paso:** medir cuántas abiertas tienen `fecha_fin_solicitud IS NULL` y revisar qué datos trae la BDNS para ellas (`abierto`, `text_fin`, fechas de inicio, antigüedad de `fecha_recepcion`).
- **Detectado:** 30-oct-2026, al verificar `sitemaps-pregenerated`.

### El contenedor descarga dependencias de desarrollo en cada arranque — Media

- **Problema:** el `Dockerfile` instala con `uv sync --no-dev`, pero el `CMD` usa `uv run`, que vuelve a sincronizar el entorno al arrancar. Los logs muestran `Downloading ruff`, `Downloading pygments`, `Installed 7 packages` en cada arranque.
- **Riesgo:** el arranque depende de la red. Si PyPI falla o tarda, el contenedor no arranca y el deploy falla.
- **Propuesta:** `CMD ["uv", "run", "--no-sync", ...]`, o ejecutar directamente `.venv/bin/uvicorn`. Verificar que el log de arranque ya no muestra descargas.
- **Detectado:** 30-oct-2026, en los logs del deploy `43a151f`.

### Reentrenar FAISS más rápido — Media

- **Problema:** una construcción completa del índice tarda **~30 min** en producción, de los que **25 son entrenamiento**. Un benchmark local (50K × 1536, 4 hilos) reparte el entrenamiento en **OPQ 863 s (98,5 %)** + IVF/PQ 13 s.
- **Cuándo importa:** solo en el reentrenamiento manual (`POST /api/admin/faiss/rebuild`) o si se pierde `faiss.index`; el arranque normal carga desde disco en ~0,1 s.
- **Opciones:** quitar OPQ (`IVF1024,PQ64`), reducir sus iteraciones (`niter`) o entrenarlo con menos vectores. **Requiere medir que la calidad de búsqueda no empeora** (recall@k frente al índice actual con consultas reales).
- **Relacionado:** `sample_embeddings` usa `ORDER BY RANDOM() LIMIT 50000`, que recorre ~4 GB de BLOBs (35 s en producción); y el pico de memoria de la construcción (~4–5 GB en un servidor de 8 GB).
- **Detectado:** 30-oct-2026. Ver `doc/tasks/faiss-persistence.md`.

---

## Otros cabos sueltos

| Tema | Prioridad | Detalle |
|---|---|---|
| Alerta cuando falla OpenAI | Media | Los fallos de embeddings (búsquedas y syncs) solo se registran en el log y la búsqueda degrada en silencio a FTS. La cuenta estuvo sin saldo sin que nadie lo notara. Reutilizar el email de alerta de los syncs |
| Secretos como *build args* en Coolify | Media | `OPENAI_API_KEY`, `ADMIN_SECRET` y `SMTP_PASSWORD` tienen marcado "Available at Buildtime" y aparecen como build args (aviso `SecretsUsedInArgOrEnv`). Desmarcarlo en Coolify; no requiere código |
| Límite de memoria del contenedor | Baja | `memory.max = max`: si la app se pasa de memoria, el OOM lo resuelve el kernel del servidor y puede afectar a otros servicios. Valorar un límite en Coolify (con margen para una construcción de FAISS) |
| Borrar `idx_conv_sitemap` | Baja | Redundante con los índices de `sitemap-covering-index.md`. Borrarlo es irreversible y no aporta casi nada; revisar antes los planes de consulta |
| README desactualizado | Baja | Indica el puerto 8000 para desarrollo (Vite hace proxy a 8001) y una tabla de variables de entorno incompleta (la completa está en `doc/OPERACIONES.md`) |
| `CLAUDE.md` en `.gitignore` | Baja | No se versiona; `AGENTS.md` sí. Decidir si versionar los dos |
