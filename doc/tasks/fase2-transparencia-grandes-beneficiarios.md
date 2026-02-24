# Plan: Pagina de Grandes Beneficiarios (Fase 2 — Transparencia)

## Contexto

Fase 2 del roadmap. Crear una pagina `/transparencia` que muestre un ranking visual de los mayores receptores de dinero publico en España, con datos en tiempo real de la BDNS (~126.000 registros). Al hacer click en un beneficiario, se despliegan sus concesiones individuales (reutilizando el endpoint existente de concesiones por NIF/CIF), creando un audit trail completo: ranking → concesiones → detalle de ayuda → fuente oficial.

---

## Archivos a modificar/crear

| Archivo | Accion | Descripcion |
|---------|--------|-------------|
| `backend/services/bdns_client.py` | Modificar | Añadir `search_top_beneficiaries()` y `get_top_beneficiaries_years()` |
| `backend/routes/beneficiarios.py` | **Crear** | Rutas: `/api/beneficiarios-top` y `/api/beneficiarios-top/anios` |
| `backend/routes/__init__.py` | Modificar | Registrar nuevo router |
| `backend/main.py` | Modificar | Incluir nuevo router |
| `frontend/src/utils/api.js` | Modificar | Añadir `searchTopBeneficiaries()` y `getTopBeneficiariesYears()` |
| `frontend/src/utils/tracking.js` | Modificar | Añadir eventos de transparencia |
| `frontend/src/components/BeneficiaryRow.js` | **Crear** | Fila con barra visual + drill-down de concesiones |
| `frontend/src/pages/transparencia.js` | **Crear** | Pagina de ranking con filtros (año, NIF/CIF) |
| `frontend/src/components/Header.js` | Modificar | Añadir enlace de navegacion a Transparencia |
| `frontend/src/main.js` | Modificar | Registrar ruta + handlers de filtros y drill-down |
| `backend/tests/test_beneficiarios.py` | **Crear** | Tests del endpoint proxy |
| `frontend/tests/beneficiaryRow.test.js` | **Crear** | Tests del componente y parsing de nombres |

---

## Paso 1: Backend — BDNS Client

En `backend/services/bdns_client.py`, añadir dos metodos:

### `search_top_beneficiaries(params)`
- Endpoint BDNS: `GET /grandesbeneficiarios/busqueda`
- Params: page, pageSize, order, direccion, anios (array), nifCif
- Este endpoint NO usa `vpd` segun la OpenAPI spec
- Cache TTL: `CACHE_TTL_DETAIL` (1 hora)
- Cache key prefix: `"top_beneficiaries"`

### `get_top_beneficiaries_years()`
- Endpoint BDNS: `GET /grandesbeneficiarios/anios`
- Sin parametros
- Cache TTL: `CACHE_TTL_CATALOGS` (24 horas)
- Cache key: `"top_beneficiaries:years"`

---

## Paso 2: Backend — Ruta nueva

Crear `backend/routes/beneficiarios.py` (siguiendo patron de `concesiones.py`):

- `GET /api/beneficiarios-top` — busqueda con filtros:
  - `page` (default: 0)
  - `pageSize` (default: 20)
  - `order` (default: ayudaETotal)
  - `direccion` (default: desc)
  - `anio` (singular int → se convierte a array `anios` internamente)
  - `nifCif` (string, optional)
- `GET /api/beneficiarios-top/anios` — lista de años disponibles

Registrar en `__init__.py` y `main.py`.

---

## Paso 3: Frontend — API + Tracking

En `api.js`: añadir `searchTopBeneficiaries(params)` y `getTopBeneficiariesYears()`.

En `tracking.js`: añadir `TRANSPARENCIA_VIEW`, `TRANSPARENCIA_FILTER`, `TRANSPARENCIA_DRILL_DOWN`.

---

## Paso 4: Frontend — Componente BeneficiaryRow

Crear `frontend/src/components/BeneficiaryRow.js`:

### Funciones:
- **`parseTopBeneficiaryName(raw)`** — extrae NIF/CIF y nombre limpio:
  - Input: `"ES A07129430 AIR EUROPA LINEAS AEREAS, SA"`
  - Output: `{nifCif: "A07129430", name: "AIR EUROPA LINEAS AEREAS, SA"}`

- **`createBeneficiaryRow(item, rank, maxAmount)`** — cada fila muestra:
  - Numero de ranking (izquierda)
  - Nombre del beneficiario (limpio, truncado)
  - NIF/CIF en gris mono
  - Barra horizontal proporcional (CSS puro, % relativo al max de la pagina, min 2%)
  - Importe formateado (derecha)
  - Boton expandir para drill-down de concesiones
  - Atributo `data-nif-cif` para el drill-down

- **`createBeneficiaryList(items, startRank)`** — wrapper que calcula maxAmount

### Drill-down de concesiones:
- Cada fila tiene boton "Ver concesiones" (icono expandir)
- Click → carga concesiones via `/api/concesiones?nifCif=X` (endpoint existente)
- Se muestran inline debajo de la fila usando `createConcessionList()` de `ConcessionCard.js`
- Cada concesion muestra la convocatoria asociada → enlaza al detalle → fuente oficial BDNS
- **Audit trail:** Ranking → Concesiones → Detalle ayuda → Fuente oficial

---

## Paso 5: Frontend — Pagina transparencia.js

Crear `frontend/src/pages/transparencia.js`:

- **Header**: titulo "Transparencia" + descripcion con link a fuente oficial
- **Filtros**: select de año (desde `/anios`, default: mas reciente) + input NIF/CIF + boton "Filtrar"
- **Contador**: "X grandes beneficiarios en 2024"
- **Ranking**: lista de BeneficiaryRow con barras visuales
- **Paginacion**: reutiliza `createPagination` existente
- **Logica default**: si no hay `anio` en params, auto-selecciona el mas reciente

---

## Paso 6: Frontend — Header + main.js

### Header.js
Reemplazar tagline `"Busca ayudas y subvenciones publicas"` por `<nav>` con link a `/transparencia`.

### main.js
- Import `renderTransparenciaPage`
- `registerRoute('/transparencia', handler)` con renderLoading + tracking
- En `setupEventListeners()`:
  - Listener para form `#transparencia-filters` → `handleTransparenciaFilter`
  - Listener para botones drill-down → `handleBeneficiaryDrillDown`
- **`handleTransparenciaFilter`**: lee FormData, navega a `/transparencia?anio=X&nifCif=Y`
- **`handleBeneficiaryDrillDown`**: carga concesiones por NIF/CIF, inserta debajo de la fila

---

## Paso 7: Tests

### Backend (`backend/tests/test_beneficiarios.py`)
- [x] Test busqueda con filtro de año
- [x] Test busqueda con NIF/CIF
- [x] Test sort por defecto (ayudaETotal desc)
- [x] Test endpoint de años

### Frontend (`frontend/tests/beneficiaryRow.test.js`)
- [x] Test `parseTopBeneficiaryName` con formato "ES NIF NOMBRE"
- [x] Test `parseTopBeneficiaryName` con formato sin ES
- [x] Test `parseTopBeneficiaryName` con null/empty
- [x] Test `createBeneficiaryRow` renderiza rank, nombre, importe, barra proporcional

---

## Verificacion end-to-end

1. `uv run pytest -v` — tests backend pasan
2. `cd frontend && bun run test:run` — tests frontend pasan
3. Arrancar backend + frontend en dev
4. Navegar a `/transparencia` — carga ranking del año mas reciente
5. Cambiar año en dropdown → datos se actualizan
6. Buscar por NIF/CIF → filtra correctamente
7. Click en beneficiario → despliega concesiones individuales
8. Click en convocatoria de concesion → navega al detalle con link a fuente oficial
9. Paginacion funciona
10. Responsive en movil
11. Link "Transparencia" en header visible y funcional