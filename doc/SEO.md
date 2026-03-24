# Plan de Accion SEO - Hola Ayudas

> Ultima actualizacion: 2026-03-24

## Estado Actual

Auditoria completa realizada el 2026-03-24. SEO tecnico base implementado (meta tags, OG, canonical, seo.js dinamico, JSON-LD en detalle). Gaps criticos: no existe sitemap.xml, falta schema en homepage, OG image con dimensiones incorrectas.

---

## Estrategia

Hola Ayudas tiene una oportunidad SEO unica: las ~600K paginas de detalle de convocatorias pueden posicionarse para queries long-tail que la web del gobierno maneja mal debido a su UX deficiente y falta de optimizacion SEO.

### Fuentes de Trafico

| Canal | Fase | Estado |
|-------|------|--------|
| Referidos de HolaDatos (enlaces en publicaciones) | 0-1 | Activo |
| Busqueda organica (long-tail convocatorias) | 2+ | Pendiente — requiere sitemap dinamico |
| Busqueda organica (keywords genericas) | 3+ | Futuro |

---

## Estrategia de Keywords

### Analisis de Competencia

| Categoria | Keywords | Competencia | Estrategia |
|----------|----------|-------------|----------|
| Oportunidad alta | "ayudas autonomos 2026", "subvenciones pymes" | Media | Landing pages por audiencia (futuro) |
| Oportunidad media | "ayudas digitalizacion", "subvenciones cultura" | Media | Paginas por categoria (futuro) |
| Competencia baja | "consultar convocatoria BDNS", "buscar subvenciones publicas" | Baja | SEO de la homepage |
| Long-tail | "ayudas para emprendedores en [CCAA]", "convocatoria BDNS 886707" | Muy baja | **600K paginas de detalle** ← mayor oportunidad |

### Keywords Objetivo

| Keyword | Intencion | Tipo de Contenido |
|---------|-----------|-------------------|
| "buscar ayudas publicas" | Navegacional | Homepage |
| "subvenciones abiertas 2026" | Informativa | Pagina de ultimas ayudas |
| "ayudas autonomos [CCAA]" | Transaccional | Busqueda con filtros |
| "convocatoria BDNS [numero]" | Navegacional | Pagina de detalle |
| "quien recibe subvenciones" | Informativa | Pagina de beneficiarios |

---

## Implementacion SEO — Checklist

### Fase 1: Fundamentos (completado)

- [x] Meta tags basicos (title, description, viewport, charset, theme-color)
- [x] Open Graph tags (og:type, og:title, og:description, og:url, og:site_name, og:locale, og:image)
- [x] Twitter Card tags (summary_large_image)
- [x] URL canonical en index.html
- [x] `robots.txt` con Allow + referencia a sitemap
- [x] Mobile-friendly (responsive, mobile-first)
- [x] URLs limpias y SEO-friendly (`/buscar`, `/ayuda/:id`, `/beneficiarios`, `/estadisticas`)
- [x] `seo.js` — actualizacion dinamica de meta tags por ruta SPA
- [x] JSON-LD BreadcrumbList en paginas de detalle
- [x] JSON-LD GovernmentService en paginas de detalle
- [x] HTML semantico basico (header, nav, main, footer, article)
- [x] Heading hierarchy (h1 por pagina, h2/h3 secciones)
- [x] Favicon SVG

### Fase 2: SEO Tecnico Critico (completado)

- [x] **Sitemap dinamico** — index segmentado: open batches + closed by year + static (`backend/routes/seo.py`)
- [x] **Corregir OG image** — 1200x630px PNG con logo "ha" + nombre + subtitulo
- [x] **Schema WebSite + SearchAction en homepage** — habilita sitelinks search box en Google
- [x] **Schema Organization en homepage** — identifica HolaDatos como proveedor
- [x] **Pagina 404 real** — muestra pagina de error con links a inicio y busqueda (`router.js` + `main.js`)
- [x] **Titles dinamicos en `/beneficiarios`** — incluye año y query activos en title y description
- [x] **`rel="next"`/`rel="prev"`** en resultados paginados (`seo.js` + `Pagination.js` data attrs + `main.js`)
- [x] **Focus management en navegacion SPA** — focus a `<main>` tras render + `scrollTo(0,0)` + outline oculto para mouse

### Fase 3: Mejoras (futuro)

- [ ] Seccion de FAQ
- [ ] Landing pages estaticas por segmento de audiencia
- [ ] `og:image:alt` en todas las paginas
- [ ] `twitter:site` y `twitter:creator` con handle de HolaDatos
- [ ] Skip-to-content link (accesibilidad)
- [ ] Aria-labels en controles interactivos (filtros, sort, botones)

---

## Sitemap Dinamico — Diseño Detallado

### Contexto

- ~600K convocatorias totales en SQLite local
- ~200K abiertas (abiertas, sin info, permanente)
- ~400K cerradas, distribuidas por año
- Limite protocolo sitemap: 50,000 URLs por archivo

### Estructura

```
/sitemap.xml                              ← Sitemap Index
│
├── /sitemap-static.xml                   ← 6 URLs (home, buscar, beneficiarios, estadisticas, concesiones, contacto)
│
├── /sitemap-grants-open-1.xml            ← Ayudas abiertas batch 1 (≤50K)
├── /sitemap-grants-open-2.xml            ← batch 2
├── /sitemap-grants-open-3.xml            ← batch 3
├── /sitemap-grants-open-4.xml            ← batch 4
│
├── /sitemap-grants-closed-2026.xml       ← Cerradas 2026
├── /sitemap-grants-closed-2026-2.xml     ← Overflow si >50K en un año
├── /sitemap-grants-closed-2025.xml       ← Cerradas 2025
├── /sitemap-grants-closed-2024.xml       ← ...
└── ...
```

### Prioridades y frecuencia por segmento

| Segmento | ~URLs | Sitemaps | `changefreq` | `priority` | Razon |
|----------|-------|---------|-------------|-----------|-------|
| Estaticas | 6 | 1 | `daily` | `1.0` / `0.9` | Paginas core |
| Abiertas (~200K) | 200K | 4-5 | `weekly` | `0.8` | Contenido activo, puede cambiar estado/deadline |
| Cerradas año actual | variable | 1-2 | `monthly` | `0.4` | Aun se cierran convocatorias |
| Cerradas años anteriores | ~60-80K/año | 1-2/año | `yearly` | `0.3` | Contenido archival estable |

### Implementacion backend

Nuevo archivo: `backend/routes/sitemap.py`

```
GET /sitemap.xml               ← Index: enumera hijos dinamicamente
GET /sitemap-static.xml        ← Hardcoded, 6 URLs
GET /sitemap-grants-{seg}.xml  ← Query SQL → XML
```

#### Generacion on-demand con cache

No se pre-generan archivos. Cada request ejecuta query SQL y devuelve XML, con cache en memoria:

| Sitemap | Cache TTL | Razon |
|---------|-----------|-------|
| `sitemap.xml` (index) | 1h | Rara vez cambian los hijos |
| `sitemap-static.xml` | 24h | Casi nunca cambia |
| `sitemap-grants-open-*.xml` | 1h | Ayudas pueden cambiar de estado |
| `sitemap-grants-closed-{año_actual}.xml` | 6h | Aun se cierran convocatorias |
| `sitemap-grants-closed-{años_pasados}.xml` | 24h | No cambian |

#### Invalidacion tras sync

Cuando el sync diario de convocatorias termina, invalida solo los caches afectados:

```python
async def on_sync_complete():
    sitemap_cache.invalidate("open-*")                  # Abiertas pudieron cambiar
    sitemap_cache.invalidate(f"closed-{current_year}")   # Solo año en curso
    # closed-2024, closed-2023... no se tocan
```

#### `lastmod` en sitemap index

Clave para crawl budget — Google re-crawlea solo hijos con `lastmod` reciente:

```xml
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://www.holaayudas.com/sitemap-grants-open-1.xml</loc>
    <lastmod>2026-03-24T08:00:00+01:00</lastmod>  <!-- ultimo sync -->
  </sitemap>
  <sitemap>
    <loc>https://www.holaayudas.com/sitemap-grants-closed-2024.xml</loc>
    <lastmod>2025-12-31T23:59:00+01:00</lastmod>  <!-- congelado -->
  </sitemap>
</sitemapindex>
```

#### Compresion

Servir con `Content-Type: application/xml` y gzip via middleware FastAPI. Un sitemap de 50K URLs ≈ 2-3MB sin comprimir, ~200KB comprimido.

#### `lastmod` por URL

Usar `fecha_actualizacion` de la tabla convocatorias (fallback: `fecha_registro`). Google prioriza URLs con `lastmod` reciente.

### Flujo completo

```
Sync diario BDNS → SQLite (ya existe)
         │
         ├── INSERT nuevas convocatorias
         ├── UPDATE estados (abierta → cerrada)
         └── Invalida cache sitemap (open + año actual)

Googlebot pide /sitemap.xml
         │
         ├── Cache valido → devuelve index cacheado
         └── Cache expirado → query counts → genera index → cachea

Googlebot pide /sitemap-grants-open-1.xml
         │
         ├── Cache valido → devuelve XML cacheado
         └── Cache expirado → SELECT ... LIMIT 50000 OFFSET 0 → genera XML → cachea
```

---

## Referencia de Archivos SEO

| Archivo | Proposito |
|---------|-----------|
| `frontend/src/utils/seo.js` | Utilidades SEO: updateMetaTags(), buildBreadcrumbSchema(), buildGrantSchema() |
| `frontend/index.html` | Meta tags base (OG, Twitter, canonical) |
| `frontend/public/robots.txt` | Configuracion para crawlers |
| `frontend/public/og-image.png` | Preview para redes sociales (1200x630, logo "ha") |
| `backend/routes/sitemap.py` | Sitemap dinamico (por implementar) |

---

## Diferenciadores vs Web del Gobierno

| Aspecto | infosubvenciones.es | Hola Ayudas |
|---------|--------------------:|:-----------:|
| Velocidad de carga | Lenta (Angular SPA) | Rapida (Vanilla JS) |
| Experiencia movil | Mala | Excelente (mobile-first) |
| UX de busqueda | Formularios complejos | Barra de busqueda simple + filtros |
| Legibilidad del detalle | Denso, burocratico | Limpio, estructurado |
| Deep linking | URLs no funcionales | URLs SEO-friendly |
| Compartir en redes | Sin tags OG | OG + Twitter Card completos |
| Indexacion (sitemap) | Sin sitemap publico | 600K URLs con sitemap dinamico (pendiente) |

---

## Mantenimiento

- **Post-implementacion sitemap**: Registrar sitemap en Google Search Console
- **Semanal**: Monitorizar Search Console (paginas indexadas, errores de rastreo, cobertura)
- **Mensual**: Revisar que categorias de ayudas generan mas trafico organico
- **Tras cada sync**: Cache de sitemap se invalida automaticamente
- **Al añadir paginas nuevas**: Actualizar `sitemap-static.xml` y esta checklist
