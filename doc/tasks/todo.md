# Tareas pendientes

Todas las tareas de este sprint han sido completadas.

## Completadas

### 1. Bug: Beneficiarios duplicados en Transparencia con "Todos" los años — RESUELTO

**Solución:** Agregación por `nif_cif` con `GROUP BY` + `SUM(ayuda_e_total)` en SQLite cuando `anio` es None.

- `beneficiarios_db.py`: Nueva función `get_top_beneficiarios_aggregated()` para ranking sin año
- `beneficiarios_db.py`: `search_beneficiarios()` ahora agrega por `nif_cif` cuando `anio=None`
- `beneficiarios.py`: Nueva lógica de routing — usa SQLite agregado cuando no hay año ni nifCif
- Tests: 7 nuevos tests para agregación + tests existentes actualizados

### 2. Tests — Planes de Fase 1 y Fase 2 completados

- `fase1-filtros-concesiones.md`: Tests marcados como completados
- `fase2-transparencia-grandes-beneficiarios.md`: Tests marcados como completados

### 3. Mejora: Documentos abren en visor PDF del navegador — COMPLETADO

**Solución:** Nuevo endpoint proxy `GET /api/documentos/{doc_id}` que cambia `Content-Disposition` de `attachment` a `inline` para tipos viewables (PDF, imágenes, HTML, text).

- `convocatorias.py`: Nuevo endpoint con `StreamingResponse`
- `GrantDetail.js`: URL cambiada a `/api/documentos/`, icono cambiado a "ojo/ver"
- `main.js`: Tracking actualizado para nueva URL
- Tests: 2 nuevos tests (PDF inline + ZIP attachment)

### 4. Mejora: Visibilidad del enlace Transparencia en header — COMPLETADO

**Solución:** Enlace convertido en pill/badge con `bg-primary/5 text-primary font-medium rounded-full`.

- `Header.js`: Clases CSS actualizadas
