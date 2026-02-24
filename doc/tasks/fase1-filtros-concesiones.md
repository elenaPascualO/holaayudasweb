# Plan: Filtros Avanzados + Concesiones (Fase 1)

## Contexto

Hola Ayudas tiene la Fase 0 completada (busqueda basica de convocatorias con filtros de admin, region, fecha, estado). El usuario quiere avanzar con la Fase 1: añadir filtros avanzados y la funcionalidad de concesiones (transparencia).

**Nota importante:** El usuario pidio "Sector de actividad" pero el parametro `actividades` NO existe en el endpoint `/convocatorias/busqueda` de BDNS (solo existe en `/concesiones/busqueda`). En su lugar usaremos `finalidad` (tematica de politica de gasto: Cultura, Educacion, I+D...) que cubre un caso de uso similar.

---

## Sprint 1: Filtros Avanzados

### 1.1 Backend — Nuevos parametros en busqueda de convocatorias

**Archivo:** `backend/routes/convocatorias.py`
- Añadir 3 nuevos Query params:
  - `tiposBeneficiario: str | None` (comma-separated IDs)
  - `instrumentos: str | None` (comma-separated IDs)
  - `finalidad: int | None` (single ID)
- Incluirlos en el dict `params` si no son None

**Archivo:** `backend/services/bdns_client.py` → `_build_search_params()`
- Añadir mapping para los 3 nuevos params (se pasan tal cual a BDNS, sin conversion):
  - `tiposBeneficiario` → `tiposBeneficiario`
  - `instrumentos` → `instrumentos`
  - `finalidad` → `finalidad`

### 1.2 Frontend — Cache de catalogos

**Nuevo archivo:** `frontend/src/utils/catalogCache.js`
- Funcion `getCatalogs()` que:
  - Hace fetch a `/api/catalogo/instrumentos`, `/api/catalogo/beneficiarios`, `/api/catalogo/finalidades` en paralelo
  - Cachea el resultado en variable de modulo (una sola llamada por sesion)
  - Devuelve `{ instrumentos, beneficiarios, finalidades }` — cada uno array de `{id, descripcion}`
- Patron similar a como `regionCache.js` exporta datos, pero dinamico

### 1.3 Frontend — Nuevos dropdowns en FilterPanel

**Archivo:** `frontend/src/components/FilterPanel.js`
- Añadir 3 nuevos `<select>` desplegables tras la seccion de Regiones:
  1. **"Tipo de ayuda"** → param `instrumentos`, datos de catalogo instrumentos
  2. **"¿Para quien?"** → param `tiposBeneficiario`, datos de catalogo beneficiarios
  3. **"Tematica"** → param `finalidad`, datos de catalogo finalidades
- Cada select tiene opcion "Todas" por defecto (sin valor)
- `createFilterPanel()` recibe nuevo param `catalogs` con los datos
- Valores actuales se leen de `currentFilters.instrumentos`, etc.
- `hasActiveFilters()` incluye los nuevos filtros

### 1.4 Frontend — Integracion en paginas

**Archivo:** `frontend/src/pages/search.js`
- Importar `getCatalogs` de catalogCache
- Llamar `getCatalogs()` al inicio del render (antes de la API de busqueda)
- Leer nuevos params de URL: `instrumentos`, `tiposBeneficiario`, `finalidad`
- Pasarlos al `searchGrants()` y al `createFilterPanel()`
- Incluirlos en `baseParams` para preservar en paginacion

**Archivo:** `frontend/src/pages/home.js`
- Importar y llamar `getCatalogs()` para pasar datos al FilterPanel
- Los filtros del home ya redirigen a /buscar con params

### 1.5 Tests

- [ ] Backend: test en `backend/tests/test_convocatorias.py` para los nuevos params
- [ ] Frontend: test en `frontend/tests/catalogCache.test.js` para getCatalogs()

---

## Sprint 2: Concesiones desde detalle

### 2.1 Backend — Endpoint de concesiones

**Archivo:** `backend/services/bdns_client.py`
- Nueva funcion `search_concesiones(params)`:
  - Llama a `/concesiones/busqueda` con los params convertidos
  - Cache prefix: "concesiones", TTL: 5 min (mismo que busquedas)
  - Params principales: `numeroConvocatoria`, `nifCif`, `page`, `pageSize`, `vpd=GE`

**Nuevo archivo:** `backend/routes/concesiones.py`
- `GET /api/concesiones` — busqueda general de concesiones
  - Params: `bdnsCode` (codigo de convocatoria), `nifCif`, `page`, `pageSize`
- Registrar router en `backend/main.py`

### 2.2 Frontend — API client

**Archivo:** `frontend/src/utils/api.js`
- Nueva funcion `getConcesionesByGrant(bdnsCode, page = 0)`:
  - `GET /api/concesiones?bdnsCode={bdnsCode}&page={page}&pageSize=20`
- Nueva funcion `searchConcesiones(params)` para busqueda general

### 2.3 Frontend — Seccion en detalle de convocatoria

**Archivo:** `frontend/src/components/GrantDetail.js`
- Nueva seccion "¿Quien recibio esta ayuda?" al final del detalle
- Boton "Ver beneficiarios" que al hacer click:
  - Llama a `getConcesionesByGrant(bdnsCode)`
  - Muestra lista de ConcessionCards
  - Paginacion si hay mas resultados
- Si no hay concesiones, mostrar mensaje "No hay concesiones registradas"

**Nuevo archivo:** `frontend/src/components/ConcessionCard.js`
- Tarjeta compacta con:
  - Nombre del beneficiario (parseado: quitar NIF del inicio si va junto)
  - Importe (formateado con `formatCurrency`)
  - Fecha de concesion
  - Tipo de instrumento
- Patron visual similar a GrantCard pero mas compacto

### 2.4 Frontend — Wiring en main.js

**Archivo:** `frontend/src/main.js`
- Event handler para click en boton "Ver beneficiarios" (event delegation con data-attribute)
- Tracking event para analytics

### 2.5 Tests

- [ ] Backend: `backend/tests/test_concesiones.py` — test del nuevo endpoint
- [ ] Frontend: `frontend/tests/concessionCard.test.js` — test del componente

---

## Sprint 3: Pagina de busqueda de concesiones (opcional, despues)

- [ ] Pagina standalone `/concesiones` con busqueda por NIF/CIF
- [ ] Link en el header de navegacion
- [ ] Reutiliza ConcessionCard y el endpoint existente

---

## Resumen de archivos

### Modificados:
| Archivo | Cambio |
|---------|--------|
| `backend/routes/convocatorias.py` | 3 nuevos Query params |
| `backend/services/bdns_client.py` | Mapping nuevos params + `search_concesiones()` |
| `backend/main.py` | Registrar concesiones router |
| `frontend/src/components/FilterPanel.js` | 3 nuevos dropdowns |
| `frontend/src/components/GrantDetail.js` | Seccion concesiones |
| `frontend/src/pages/search.js` | Catalogs + nuevos params |
| `frontend/src/pages/home.js` | Catalogs |
| `frontend/src/utils/api.js` | Funciones concesiones |
| `frontend/src/main.js` | Event handlers |

### Nuevos:
| Archivo | Proposito |
|---------|-----------|
| `frontend/src/utils/catalogCache.js` | Fetch/cache de catalogos |
| `backend/routes/concesiones.py` | Endpoint concesiones |
| `frontend/src/components/ConcessionCard.js` | Tarjeta concesion |

---

## Verificacion

1. **Filtros:** Buscar convocatorias con cada filtro nuevo individualmente y combinados — verificar que los resultados cambian
2. **Concesiones:** Ir a una ayuda conocida con concesiones (ej. buscar una del 2024), click en "Ver beneficiarios", verificar que aparecen
3. **Tests:** `uv run pytest -v` + `cd frontend && bun run test:run`
4. **Responsive:** Verificar que los nuevos dropdowns y la seccion de concesiones se ven bien en movil

---

## Orden de implementacion

1. Sprint 1 primero (filtros) — mejora la busqueda existente
2. Sprint 2 despues (concesiones) — nueva funcionalidad
3. Sprint 3 es opcional y puede hacerse mas adelante