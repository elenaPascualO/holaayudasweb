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

## Despliegue en Railway

### Prerrequisitos
- Repositorio en GitHub
- Cuenta de Railway

### Archivos de Despliegue

| Archivo | Proposito |
|---------|-----------|
| `Dockerfile` | Build multi-stage (Bun frontend + Python backend) |
| `railway.json` | Configuracion de Railway |

### Variables de Entorno

| Variable | Valor | Requerida |
|----------|-------|-----------|
| `ENVIRONMENT` | `production` | Si |
| `ALLOWED_ORIGINS` | `https://www.holaayudas.com` | Si |
| `BDNS_BASE_URL` | `https://www.infosubvenciones.es/bdnstrans/api` | No (default) |
| `DISCORD_WEBHOOK_URL` | `https://discord.com/api/webhooks/...` | Si (para feedback) |

### Configuracion de Dominio Personalizado

#### Lado Railway
1. Settings > Networking > Custom Domain
2. Añadir `www.holaayudas.com`

#### Lado DNS
| Tipo | Host | Valor |
|------|------|-------|
| CNAME | `www.holaayudas.com` | `[dominio-railway].up.railway.app` |
| Redirect 301 | `holaayudas.com` | `https://www.holaayudas.com` |
