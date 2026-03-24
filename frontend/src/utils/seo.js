/**
 * SEO utilities — update meta tags, canonical URLs, and JSON-LD on SPA navigation.
 */

const BASE_URL = 'https://www.holaayudas.com'
const SITE_NAME = 'Hola Ayudas'
const DEFAULT_DESCRIPTION = 'Busca ayudas y subvenciones publicas en España de forma facil y rapida. Gratis y sin registro.'
const DEFAULT_IMAGE = `${BASE_URL}/og-image.png`

/**
 * Set or create a <meta> tag.
 * @param {string} attr - Attribute name ('name' or 'property')
 * @param {string} value - Attribute value (e.g. 'og:title')
 * @param {string} content - Content value
 */
function setMeta(attr, value, content) {
  let el = document.querySelector(`meta[${attr}="${value}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, value)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

/**
 * Set or create a <link> tag.
 * @param {string} rel - Rel attribute (e.g. 'canonical')
 * @param {string} href - Href value
 */
function setLink(rel, href) {
  let el = document.querySelector(`link[rel="${rel}"]`)
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', rel)
    document.head.appendChild(el)
  }
  el.setAttribute('href', href)
}

/**
 * Inject or replace JSON-LD structured data in <head>.
 * @param {Object|Object[]} schemas - One or more JSON-LD objects
 */
function setJsonLd(schemas) {
  // Remove existing JSON-LD
  document.querySelectorAll('script[type="application/ld+json"][data-seo]').forEach(el => el.remove())

  const items = Array.isArray(schemas) ? schemas : [schemas]
  for (const schema of items) {
    const script = document.createElement('script')
    script.type = 'application/ld+json'
    script.dataset.seo = '1'
    script.textContent = JSON.stringify(schema)
    document.head.appendChild(script)
  }
}

/**
 * Build a BreadcrumbList schema.
 * @param {Array<{name: string, url: string}>} items - Breadcrumb items
 * @returns {Object} JSON-LD BreadcrumbList
 */
export function buildBreadcrumbSchema(items) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    'itemListElement': items.map((item, i) => ({
      '@type': 'ListItem',
      'position': i + 1,
      'name': item.name,
      'item': item.url,
    })),
  }
}

/**
 * Build a GovernmentService schema for a grant detail page.
 * @param {Object} grant - Grant detail object from API
 * @returns {Object} JSON-LD GovernmentService
 */
export function buildGrantSchema(grant) {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'GovernmentService',
    'name': grant.descripcion || '',
    'serviceType': 'Subvencion publica',
    'provider': {
      '@type': 'GovernmentOrganization',
      'name': [grant.organo?.nivel3, grant.organo?.nivel2, grant.organo?.nivel1]
        .filter(Boolean)
        .join(' - '),
    },
  }

  if (grant.descripcionFinalidad) {
    schema.category = grant.descripcionFinalidad
  }

  if (grant.presupuestoTotal) {
    schema.offers = {
      '@type': 'Offer',
      'price': grant.presupuestoTotal,
      'priceCurrency': 'EUR',
    }
  }

  if (grant.fechaFinSolicitud) {
    schema.availableThrough = grant.fechaFinSolicitud
  }

  return schema
}

/**
 * Build WebSite + SearchAction schema for the homepage.
 * Enables Google sitelinks search box.
 * @returns {Object} JSON-LD WebSite
 */
export function buildWebSiteSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    'name': SITE_NAME,
    'url': BASE_URL,
    'description': DEFAULT_DESCRIPTION,
    'potentialAction': {
      '@type': 'SearchAction',
      'target': `${BASE_URL}/buscar?q={search_term_string}`,
      'query-input': 'required name=search_term_string',
    },
  }
}

/**
 * Build Organization schema for the homepage.
 * @returns {Object} JSON-LD Organization
 */
export function buildOrganizationSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    'name': 'HolaDatos',
    'url': BASE_URL,
    'logo': `${BASE_URL}/favicon.svg`,
    'description': 'Datos publicos accesibles para todos. Hola Ayudas es un proyecto de HolaDatos.',
  }
}

/**
 * Set rel="next" and rel="prev" link tags for paginated pages.
 * Removes stale pagination links from previous pages.
 * @param {Object} opts
 * @param {number} opts.currentPage - Current page (0-indexed)
 * @param {number} opts.totalPages - Total number of pages
 * @param {string} opts.baseUrl - Base URL without page param (e.g. "/buscar?q=test")
 */
export function updatePaginationLinks({ currentPage, totalPages, baseUrl }) {
  // Remove existing pagination links
  document.querySelectorAll('link[rel="prev"][data-seo-pag], link[rel="next"][data-seo-pag]')
    .forEach(el => el.remove())

  if (totalPages <= 1) return

  const sep = baseUrl.includes('?') ? '&' : '?'

  if (currentPage > 0) {
    const link = document.createElement('link')
    link.rel = 'prev'
    link.href = `${BASE_URL}${baseUrl}${sep}page=${currentPage - 1}`
    link.dataset.seoPag = '1'
    document.head.appendChild(link)
  }

  if (currentPage < totalPages - 1) {
    const link = document.createElement('link')
    link.rel = 'next'
    link.href = `${BASE_URL}${baseUrl}${sep}page=${currentPage + 1}`
    link.dataset.seoPag = '1'
    document.head.appendChild(link)
  }
}

/**
 * Update all SEO meta tags for the current page.
 * @param {Object} opts
 * @param {string} [opts.title] - Page title
 * @param {string} [opts.description] - Meta description
 * @param {string} [opts.path] - URL path (e.g. '/ayuda/886707')
 * @param {string} [opts.image] - OG image URL
 * @param {Object|Object[]} [opts.jsonLd] - JSON-LD structured data
 */
export function updateMetaTags({ title, description, path, image, jsonLd } = {}) {
  const fullTitle = title
    ? `${title} | ${SITE_NAME}`
    : `${SITE_NAME} - Busca ayudas y subvenciones publicas`
  const desc = description || DEFAULT_DESCRIPTION
  const url = `${BASE_URL}${path || '/'}`
  const img = image || DEFAULT_IMAGE

  // Document title
  document.title = fullTitle

  // Standard meta
  setMeta('name', 'description', desc)

  // Canonical
  setLink('canonical', url)

  // Open Graph
  setMeta('property', 'og:title', fullTitle)
  setMeta('property', 'og:description', desc)
  setMeta('property', 'og:url', url)
  setMeta('property', 'og:image', img)

  // Twitter Card
  setMeta('name', 'twitter:title', fullTitle)
  setMeta('name', 'twitter:description', desc)
  setMeta('name', 'twitter:image', img)

  // Clean up pagination links from previous page (set fresh ones via updatePaginationLinks)
  document.querySelectorAll('link[rel="prev"][data-seo-pag], link[rel="next"][data-seo-pag]')
    .forEach(el => el.remove())

  // JSON-LD
  if (jsonLd) {
    setJsonLd(jsonLd)
  } else {
    // Remove stale JSON-LD from previous page
    document.querySelectorAll('script[type="application/ld+json"][data-seo]').forEach(el => el.remove())
  }
}
