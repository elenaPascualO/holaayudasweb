# Hola Ayudas

Interfaz web moderna y gratuita para buscar ayudas y subvenciones publicas españolas. Alternativa con mejor experiencia de usuario a la web oficial del gobierno ([infosubvenciones.es](https://www.infosubvenciones.es)).

Los datos provienen de la API publica de la **BDNS** (Base de Datos Nacional de Subvenciones).

## Funcionalidades

- Busqueda de convocatorias por texto libre
- Filtros por region, tipo de administracion y rango de fechas
- Vista detallada de cada convocatoria con estado (abierta/cerrada), plazos y enlace directo a la sede electronica
- Deep linking para compartir ayudas concretas (`/ayuda/:codigoBDNS`)
- Diseño responsive (mobile-first)

## Stack Tecnico

| Componente | Tecnologia |
|------------|------------|
| Frontend | Vanilla JS (ES Modules) + Vite + Tailwind CSS v4 |
| Backend | Python 3.13+ / FastAPI |
| Runtime frontend | Bun |
| Package manager backend | uv |
| Testing | Vitest + jsdom (frontend) / pytest (backend) |
| Deploy | Railway (Docker multi-stage) |

## Requisitos

- [Bun](https://bun.sh/) >= 1.0
- [Python](https://www.python.org/) >= 3.13
- [uv](https://docs.astral.sh/uv/) >= 0.4

## Instalacion

```bash
# Backend (desde la raiz del proyecto)
uv sync

# Frontend
cd frontend
bun install
```

## Desarrollo

```bash
# Terminal 1: Backend (desde la raiz)
uv run uvicorn backend.main:app --reload --port 8000

# Terminal 2: Frontend (desde frontend/)
cd frontend
bun run dev
```

El frontend arranca en `http://localhost:5173` y usa un proxy para redirigir `/api` al backend en `http://localhost:8000`.

## Tests

```bash
# Backend
uv run pytest -v

# Frontend
cd frontend
bun run test:run
```

## Build de produccion

```bash
cd frontend
bun run build   # Genera frontend/dist/
```

O usando Docker:

```bash
docker build -t holaayudas .
docker run -p 8000:8000 holaayudas
```

## Arquitectura

```
Cliente  -->  Frontend (Vite/Vanilla JS)  -->  Backend (FastAPI + cache)  -->  API BDNS
```

El backend actua como proxy con cache en memoria hacia la API publica de BDNS. Se encarga de:

- **CORS** — la API de BDNS no permite peticiones desde el navegador
- **Cache** — reduce la carga sobre los servidores del gobierno (catalogos 24h, busquedas 5min, detalle 1h)
- **Transformacion de fechas** — convierte de ISO a `dd/mm/yyyy` que requiere la API upstream

## Variables de Entorno

| Variable | Default | Descripcion |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | `development` o `production` |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Origenes CORS permitidos |
| `BDNS_BASE_URL` | `https://www.infosubvenciones.es/bdnstrans/api` | URL de la API upstream |
| `CACHE_TTL_CATALOGS` | `86400` | TTL cache de catalogos (segundos) |
| `CACHE_TTL_SEARCH` | `300` | TTL cache de busquedas (segundos) |
| `CACHE_TTL_DETAIL` | `3600` | TTL cache de detalle (segundos) |

## Estructura del Proyecto

```
holaayudasweb/
├── frontend/              # Vite + Vanilla JS + Tailwind CSS v4
│   ├── src/
│   │   ├── main.js        # Entry point
│   │   ├── router.js      # SPA router (History API)
│   │   ├── components/    # Componentes UI
│   │   ├── pages/         # Paginas (home, search, detail)
│   │   └── utils/         # API client, formateadores, fechas
│   └── tests/
├── backend/               # FastAPI proxy + cache
│   ├── main.py            # App FastAPI
│   ├── config.py          # Configuracion
│   ├── routes/            # Endpoints
│   ├── services/          # Cliente BDNS, cache
│   └── tests/
├── doc/                   # Documentacion del proyecto
├── Dockerfile             # Multi-stage build
└── pyproject.toml         # Dependencias Python
```

## Licencia

Proyecto privado. Todos los derechos reservados.