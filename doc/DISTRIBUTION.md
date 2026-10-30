# Guia de Distribucion - Hola Ayudas

> Ver `doc/DISTRIBUTION.md` de ParseWiz para la guia reutilizable de lanzamiento.

---

## Estrategia de Distribucion

Hola Ayudas tiene un modelo de distribucion diferente a ParseWiz o FacturaView. El canal principal es **HolaDatos**, no busqueda organica ni directorios de producto.

### Prioridad de Canales

| Prioridad | Canal | Razon |
|----------|-------|-------|
| **P0** | Publicaciones de HolaDatos | Integracion directa — usuarios ya interesados en ayudas |
| **P1** | Comunidades de autonomos/pymes | El publico objetivo esta ahi |
| **P2** | SEO (busqueda organica) | A largo plazo, cuando haya contenido |
| **P3** | Directorios de producto | Menor prioridad, herramienta de nicho |

---

## Fase 1: Integracion con HolaDatos

- [ ] Añadir enlaces de Hola Ayudas en las publicaciones de HolaDatos sobre ayudas
- [ ] Usar deep links (`/ayuda/:codigoBDNS`) en las publicaciones
- [ ] Trackear trafico referido desde HolaDatos
- [x] Crear tarjeta visual/preview para compartir en redes (banners HolaDatos para LinkedIn y X)

---

## Fase 2: Comunidades de Nicho

### Autonomos y PYMEs
| Comunidad | URL | Notas |
|-----------|-----|-------|
| Foros de autonomos | Varios foros | Compartir como herramienta util |
| Grupos de Facebook | "Autonomos en España" etc. | Post genuino, sin spam |
| Reddit r/SpainPolitics | reddit.com | Angulo de transparencia |
| Twitter/X | #autonomos #subvenciones | Compartir con audiencia de HolaDatos |

### Plantilla de Mensaje
> "Hemos creado una web gratuita para buscar ayudas y subvenciones publicas de forma facil. La web del gobierno (infosubvenciones.es) tiene un UX bastante malo, asi que hicimos una alternativa moderna. Sin registro, sin publicidad."

---

## Fase 3: Directorios de Producto

- [ ] Product Hunt (si hay interes suficientemente general)
- [ ] Hacker News (angulo de transparencia/datos abiertos)
- [ ] Peerlist

---

## Despliegue en Coolify (Hetzner)

La app se despliega con **Coolify** en un servidor **Hetzner** (`ubuntu-8gb-hel1-1`: 8 GB de RAM, 4 vCPU). **El despliegue es manual**: un push a `master` no despliega (el webhook de despliegue automático está desactivado desde el 30-oct-2026); hay que pulsar **Deploy** en Coolify. La operación completa (variables, syncs, FAISS, sitemaps, resolución de problemas) está en `doc/OPERACIONES.md`.

### Prerrequisitos
- Repositorio en GitHub
- Servidor Hetzner con Coolify instalado

### Archivos de Despliegue

| Archivo | Proposito |
|---------|-----------|
| `Dockerfile` | Build multi-stage (Bun frontend + Python backend) |

### Configuracion en Coolify

- **Build pack:** Dockerfile. Puerto expuesto: `8000`.
- **Healthcheck:** `GET /api/health`.
- **Volumen persistente** montado en `/app/data` (bases SQLite, índice FAISS y sitemaps pregenerados).
- **Variables de entorno:** ver la tabla completa en `doc/OPERACIONES.md` §2.

### Configuracion de Dominio Personalizado

#### Lado Coolify
- En el recurso, campo **Domains**: `https://www.holaayudas.com,https://holaayudas.com`. Coolify gestiona los certificados TLS.

#### Lado DNS
| Tipo | Host | Valor |
|------|------|-------|
| A | `holaayudas.com` | IP del servidor Hetzner |
| A | `www.holaayudas.com` | IP del servidor Hetzner |

La redirección 301 de `holaayudas.com` a `https://www.holaayudas.com` la hace la propia app en producción (`WwwRedirectMiddleware` en `backend/main.py`).
