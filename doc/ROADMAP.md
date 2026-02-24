# Hola Ayudas — Roadmap

> Interfaz web moderna para buscar ayudas y subvenciones publicas (BDNS).
> Stack: Bun + Vite + Vanilla JS + Tailwind CSS (frontend) / Python + FastAPI + uv (backend)

---

## Vision

Crear la mejor experiencia de usuario para buscar ayudas publicas en España, reemplazando el UX deficiente de infosubvenciones.es. Integrado con HolaDatos para que los usuarios puedan explorar ayudas relacionadas desde las publicaciones.

---

## Fase 0 — MVP (Actual)

**Objetivo:** Lanzar una interfaz de busqueda funcional que cubra el caso de uso principal: un usuario de HolaDatos hace clic en un enlace y puede buscar/explorar ayudas con una UI moderna.

**Estado:** Completada (Febrero 2026)

### Backend (Python + FastAPI + uv)

- [x] Setup del proyecto (pyproject.toml, app FastAPI, config)
- [x] Cliente API BDNS (httpx, manejo de errores)
- [x] Cache en memoria con TTL (catalogos 24h, busquedas 5min, detalle 1h)
- [x] Endpoint proxy: `GET /api/convocatorias` (busqueda)
- [x] Endpoint proxy: `GET /api/convocatorias/ultimas` (ultimas)
- [x] Endpoint proxy: `GET /api/convocatorias/:id` (detalle)
- [x] Endpoints proxy: `GET /api/catalogo/*` (regiones, finalidades, beneficiarios, instrumentos, actividades)
- [x] Health check: `GET /api/health`
- [x] Configuracion CORS
- [x] Transformacion de formato de fecha (ISO → dd/mm/yyyy)
- [x] Tests de los endpoints proxy
- [x] Tests de la logica de cache
- [x] Tests del cliente BDNS

### Frontend (Bun + Vite + Tailwind CSS v4)

- [x] Setup del proyecto (Bun, Vite, Tailwind CSS v4)
- [x] Pagina principal con barra de busqueda y chips de filtro rapido
- [x] Feed de ultimas ayudas con filtros laterales y paginacion
- [x] Chips de filtro rapido visibles en home y en resultados de busqueda
- [x] Pagina de resultados de busqueda con paginacion
- [x] Filtros basicos: tipo de administracion, rango de fechas, region
- [x] Pagina de detalle de convocatoria con info estructurada
- [x] Indicador de estado (abierta/cerrada) con pista visual
- [x] Enlace a la sede electronica (tramitacion directa)
- [x] Deep linking (`/ayuda/:codigoBDNS`)
- [x] Diseño responsive (mobile-first)
- [x] Estados de carga
- [x] Formulario de sugerencias en el footer (notificacion via Discord webhook)
- [x] Botones destacados para bases reguladoras, fuente oficial y documentos en detalle
- [x] Filtro de estado (abiertas/cerradas)
- [x] Rango de fechas por defecto y selectores de año/mes
- [x] Ordenacion de resultados (mas recientes/antiguas)
- [x] Tarjetas de ayuda enriquecidas con estado y presupuesto
- [x] Analitica con Umami (eventos de uso, respetando privacidad)
- [x] Rate limiter global y reintentos para prevenir errores 429 de BDNS

### Infraestructura

- [x] Dockerfile (multi-stage: Bun frontend + Python backend)
- [x] Configuracion railway.json
- [x] Configuracion proxy en Vite para desarrollo

### Criterios de "Hecho" (Fase 0)
- [x] El usuario puede buscar ayudas por texto
- [x] El usuario puede filtrar por region, tipo de administracion y fecha
- [x] El usuario puede ver el detalle completo de una ayuda
- [x] Los deep links funcionan desde HolaDatos
- [x] Funciona en movil
- [X] Desplegado y accesible publicamente

### Fuera de Alcance (Fase 0)
- ~~Filtros avanzados (sector, instrumento, objetivos)~~ → Fase 1
- ~~Concesiones (quien recibio subvenciones)~~ → Fase 1
- Seccion de transparencia (grandes beneficiarios)
- Cuentas de usuario o busquedas guardadas
- Optimizacion SEO avanzada (Schema.org, landing pages, meta tags dinamicos por detalle de convocatoria)

---

## Fase 1 — Filtros Avanzados y Concesiones

**Objetivo:** Ampliar las capacidades de busqueda y añadir funcionalidades de transparencia.

**Estado:** Completada (Febrero 2026)

### Filtros Avanzados
- [x] Filtro por tipo de ayuda (instrumento: subvencion, prestamo, etc.)
- [x] Filtro por tipo de beneficiario (empresas, autonomos, personas fisicas, etc.)
- [x] Filtro por tematica/finalidad (cultura, educacion, I+D, etc.)
- [x] Cache de catalogos por sesion (una sola carga)
- [x] Filtros combinables entre si y con los existentes
- [x] Parametros preservados en paginacion y URL

### Concesiones (Transparencia)
- [x] Endpoint proxy: `GET /api/concesiones` (busqueda de concesiones)
- [x] Seccion "¿Quien recibio esta ayuda?" en detalle de convocatoria
- [x] Carga bajo demanda (boton "Ver beneficiarios")
- [x] Tarjetas de concesion con beneficiario, importe y fecha
- [x] Paginacion incremental ("Ver mas beneficiarios")
- [x] Mensaje informativo cuando no hay concesiones registradas

### Pendiente para futuras fases
- [x] Pagina standalone de concesiones por beneficiario (`/concesiones`)
- [x] Busqueda por NIF/CIF del beneficiario
- [ ] Descarga de documentos de convocatoria (PDF passthrough)
- [ ] Paginacion mejorada (scroll infinito o paginacion numerada)

---

## Fase 2 — Transparencia y SEO

**Objetivo:** Añadir funcionalidades de interes publico y trafico organico.

**Estado:** En progreso (Febrero 2026)

### Transparencia
- [x] Vista de grandes beneficiarios (`/transparencia`)
- [x] Ranking visual (grafico de barras proporcionales)
- [x] Filtro por año y NIF/CIF
- [x] Drill-down a concesiones individuales por beneficiario (preview top 5)
- [x] Pagina dedicada de concesiones por beneficiario (`/concesiones?nifCif=X&anio=Y`) con paginacion
- [x] Busqueda por nombre de beneficiario (SQLite FTS5 local)
- [x] Script de sincronizacion diaria de ~130K registros de BDNS
- [ ] Seccion de subvenciones a partidos politicos
- [ ] Comparativa año a año

### SEO
- [x] robots.txt y sitemap.xml
- [ ] Datos estructurados Schema.org
- [x] Meta tags (OG, Twitter Card)
- [x] URLs canonicas
- [x] Banners para redes sociales (LinkedIn, X)
- [ ] Paginas de detalle SEO-friendly (meta tags dinamicos por convocatoria)
- [ ] Landing pages estaticas para busquedas populares

---

## Fase 3 — Experiencia de Usuario

**Objetivo:** Pulir y añadir funcionalidades de retencion.

- [ ] Modo oscuro
- [ ] Busquedas guardadas (localStorage)
- [ ] Copiar info de ayuda al portapapeles
- [ ] Compartir ayuda via enlace/redes sociales
- [ ] PWA (instalable, cache offline de catalogos)
- [ ] i18n (ES/EN)

---

## Fase 4 — Integracion con HolaDatos

**Objetivo:** Integracion profunda con el ecosistema HolaDatos.

- [ ] Widget embebible para articulos de HolaDatos
- [ ] API propia para que HolaDatos haga previews de ayudas
- [ ] Sugerencias automaticas de ayudas segun el tema del articulo
- [ ] Analitica compartida

---

## Fase 5 — Alertas y Notificaciones

**Objetivo:** Valor proactivo para los usuarios.

- [ ] Alertas por email para nuevas ayudas que coincidan con criterios (requiere BD)
- [ ] Integracion con bot de Telegram/WhatsApp
- [ ] Feed RSS de ultimas ayudas
- [ ] Digest semanal

---

## Modelo de Monetizacion

| Fase | Estrategia |
|------|------------|
| 0-2 | 100% gratis. Prioridad: traccion y SEO |
| 3+ | Donaciones / "Invitame a un cafe" |
| 4+ | Alertas premium (email, Telegram) |
| 5+ | Acceso API para integraciones |

---

## Principios de Desarrollo

1. **Simplicidad primero** — Cada funcionalidad debe funcionar sin explicacion
2. **Velocidad** — Los resultados de busqueda deben sentirse instantaneos
3. **Privacidad** — Sin datos de usuario almacenados, arquitectura solo-proxy
4. **Mobile-first** — La mayoria de usuarios vendran de HolaDatos (redes sociales → movil)
5. **Iteracion rapida** — Lanzar, medir, ajustar
6. **Respetar el upstream** — Cachear agresivamente para no sobrecargar los servidores del gobierno
