# Hola Ayudas — Especificaciones Tecnicas

## 1. Resumen

**Nombre del producto:** Hola Ayudas
**Version:** 0.1.0 (Fase 0 - MVP)
**Proposito:** Interfaz web moderna y user-friendly para buscar ayudas y subvenciones publicas españolas a traves de la API publica de BDNS.

### 1.1 Vision
Ofrecer una forma rapida, bonita e intuitiva de buscar y explorar ayudas y subvenciones publicas del gobierno español, reemplazando el UX deficiente de infosubvenciones.es.

### 1.2 Integracion con HolaDatos
Los enlaces de Hola Ayudas se incluiran en las publicaciones de HolaDatos sobre ayudas, permitiendo a los usuarios buscar y explorar convocatorias relacionadas con una experiencia superior.

### 1.3 Estado Actual
Fase 0 (MVP) - Implementada. Backend y frontend funcionales. Pendiente despliegue en produccion. Ver `doc/ROADMAP.md` para detalle de fases.

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
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│                 │     │                  │     │                     │
│   Frontend      │────▶│   Backend/Proxy  │────▶│  API BDNS           │
│   Bun + Vite    │     │   Python/FastAPI  │     │  infosubvenciones   │
│   Tailwind CSS  │     │   + Cache en      │     │                     │
│   Vanilla JS    │     │     memoria       │     │                     │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
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
| Deploy | Railway |

### 3.3 API del Proxy Backend

El backend actua como proxy transparente con cache. Transforma las respuestas de la API BDNS de forma minima, encargandose de:
- CORS (permite el origen del frontend)
- Cache (reduce carga en los servidores del gobierno)
- Transformacion de formato de fecha (el frontend envia ISO, el backend convierte a `dd/mm/yyyy`)
- Manejo de errores (traduce errores de BDNS a mensajes amigables)

#### Endpoints del Proxy

| Nuestro Endpoint | Upstream | Cache TTL |
|-----------------|----------|-----------|
| `GET /api/convocatorias` | `/convocatorias/busqueda` | 5 min |
| `GET /api/convocatorias/ultimas` | `/convocatorias/ultimas` | 5 min |
| `GET /api/convocatorias/:id` | `/convocatorias?numConv=X` | 1 hora |
| `GET /api/concesiones` | `/concesiones/busqueda` | 5 min |
| `GET /api/beneficiarios-top` | `/grandesbeneficiarios/busqueda` | 1 hora |
| `GET /api/catalogo/regiones` | `/regiones` | 24 horas |
| `GET /api/catalogo/finalidades` | `/finalidades?vpd=GE` | 24 horas |
| `GET /api/catalogo/instrumentos` | `/instrumentos` | 24 horas |
| `GET /api/catalogo/actividades` | `/actividades` | 24 horas |
| `GET /api/catalogo/beneficiarios` | `/beneficiarios?vpd=GE` | 24 horas |
| `POST /api/feedback` | - (local + Discord webhook) | - |
| `GET /api/health` | - | - |

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
Railway (igual que ParseWiz y FacturaView)

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
