# Plan de Accion SEO - Hola Ayudas

> Ultima actualizacion: 2026-02-24

## Estado Actual: Parcialmente implementado (algunos items adelantados de Fase 2)

---

## Estrategia

Hola Ayudas tiene una oportunidad SEO unica: las paginas de detalle de convocatorias pueden posicionarse para queries long-tail que la web del gobierno maneja mal debido a su UX deficiente y falta de optimizacion SEO.

### Fuente de Trafico Primaria
- **Referidos de HolaDatos** — Usuarios que hacen clic en enlaces de publicaciones de HolaDatos sobre ayudas
- Este es el canal principal para las Fases 0-1

### Fuente de Trafico Secundaria (Fase 2+)
- **Busqueda organica** — Queries relacionadas con ayudas y subvenciones en español

---

## Estrategia de Keywords

### Analisis de Competencia

| Categoria | Keywords | Competencia | Estrategia |
|----------|----------|-------------|----------|
| Oportunidad alta | "ayudas autonomos 2026", "subvenciones pymes" | Media | Landing pages por audiencia |
| Oportunidad media | "ayudas digitalizacion", "subvenciones cultura" | Media | Paginas por categoria |
| Competencia baja | "consultar convocatoria BDNS", "buscar subvenciones publicas" | Baja | SEO de la homepage |
| Long-tail | "ayudas para emprendedores en [CCAA]" | Muy baja | Paginas dinamicas de detalle |

### Keywords Objetivo

| Keyword | Intencion | Tipo de Contenido |
|---------|-----------|-------------------|
| "buscar ayudas publicas" | Navegacional | Homepage |
| "subvenciones abiertas 2026" | Informativa | Pagina de ultimas ayudas |
| "ayudas autonomos [CCAA]" | Transaccional | Busqueda con filtros |
| "convocatoria BDNS [numero]" | Navegacional | Pagina de detalle |
| "quien recibe subvenciones" | Informativa | Seccion de transparencia |

---

## Requisitos Tecnicos SEO (Fase 2)

### Imprescindible
- [x] Meta tags (title, description, OG, Twitter Card)
- [ ] Meta tags dinamicos por pagina de detalle
- [x] robots.txt y sitemap.xml
- [ ] Schema.org (WebApplication + GovernmentService)
- [x] URLs canonicas
- [x] Mobile-friendly (responsive)

### Deseable
- [ ] Seccion de FAQ
- [ ] Blog con guias ("Como solicitar ayudas para PYMEs")
- [ ] Landing pages estaticas por segmento de audiencia

---

## Referencia de Archivos SEO

| Archivo | Proposito |
|---------|-----------|
| `frontend/public/robots.txt` | Configuracion para crawlers |
| `frontend/public/sitemap.xml` | Paginas del sitio para buscadores |
| `frontend/public/og-image.png` | Preview para redes sociales (1200x630) |
| `holadatos-banner-linkedin.*` | Banner para publicaciones en LinkedIn |
| `holadatos-banner-x.*` | Banner para publicaciones en X (Twitter) |

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

---

## Mantenimiento

- Actualizar sitemap.xml al añadir paginas estaticas nuevas
- Monitorizar Google Search Console semanalmente tras el lanzamiento de Fase 2
- Identificar que categorias de ayudas generan mas trafico
