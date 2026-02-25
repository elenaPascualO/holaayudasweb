/**
 * Concesiones page — paginated list of concesiones for a beneficiary or a grant.
 */

import { searchConcesiones, getGrantDetailCached } from '../utils/api.js'
import { createConcessionList } from '../components/ConcessionCard.js'
import { createPagination } from '../components/Pagination.js'
import { createEmptyState } from '../components/EmptyState.js'
import { formatNumber, escapeHtml } from '../utils/formatters.js'

/**
 * Render the concesiones page.
 * Supports two modes:
 * - bdnsCode: show all concesiones for a grant (from detail page)
 * - nifCif: show all concesiones for a beneficiary (from transparencia)
 * @param {Object} params - Query parameters (bdnsCode, nifCif, anio, page)
 * @returns {Promise<string>} HTML
 */
export async function renderConcesionesPage(params) {
  const bdnsCode = params.bdnsCode || ''
  const nifCif = params.nifCif || ''
  const anio = params.anio || ''
  const returnTo = params.returnTo || ''
  const page = parseInt(params.page || '0', 10)
  const pageSize = 20

  if (!bdnsCode && !nifCif) {
    return createEmptyState(
      'Faltan parametros',
      'Esta pagina necesita un parametro bdnsCode o nifCif para buscar concesiones.'
    )
  }

  // Build search params — sort by amount descending
  const searchParams = { page, pageSize, order: 'importe', direccion: 'desc' }
  if (bdnsCode) searchParams.bdnsCode = bdnsCode
  if (nifCif) searchParams.nifCif = nifCif
  if (anio) {
    searchParams.fechaDesde = `${anio}-01-01`
    searchParams.fechaHasta = `${anio}-12-31`
  }

  // Fetch concesiones and grant title (if bdnsCode mode) in parallel
  const headerCtx = { bdnsCode, nifCif, anio, returnTo, grantTitle: '' }

  const [results, grantTitle] = await Promise.all([
    searchConcesiones(searchParams).catch(() => null),
    bdnsCode ? fetchGrantTitle(bdnsCode) : Promise.resolve(''),
  ])
  headerCtx.grantTitle = grantTitle

  if (!results) {
    return `
      ${createHeader(headerCtx)}
      ${createEmptyState(
        'Error al cargar',
        'No se pudo conectar con el servidor. Intentalo de nuevo.'
      )}
    `
  }

  const items = results.content || []
  if (items.length === 0) {
    const emptyLabel = bdnsCode
      ? `la convocatoria ${escapeHtml(bdnsCode)}`
      : escapeHtml(nifCif)
    return `
      ${createHeader(headerCtx)}
      ${createEmptyState(
        'Sin concesiones',
        `No se encontraron concesiones para ${emptyLabel}${anio ? ` en ${anio}` : ''}.`
      )}
    `
  }

  // For nifCif mode, extract beneficiary name from first result
  if (nifCif && !headerCtx.grantTitle) {
    const rawName = items[0].beneficiario || items[0].denominacion || nifCif
    headerCtx.beneficiaryName = parseBeneficiaryName(rawName)
  }

  const total = results.totalElements || items.length

  // Build base URL for pagination
  const baseParams = new URLSearchParams()
  if (bdnsCode) baseParams.set('bdnsCode', bdnsCode)
  if (nifCif) baseParams.set('nifCif', nifCif)
  if (anio) baseParams.set('anio', anio)
  if (returnTo) baseParams.set('returnTo', returnTo)
  const baseUrl = `/concesiones?${baseParams.toString()}`

  // For bdnsCode mode, show convocatoria link on each card
  const showConvocatoria = !bdnsCode

  return `
    ${createHeader(headerCtx)}

    <p class="text-sm text-gray-400 mb-4">
      ${formatNumber(total)} concesion${total !== 1 ? 'es' : ''}${anio ? ` en ${anio}` : ''}, ordenadas por importe
    </p>

    ${createConcessionList(items, { showConvocatoria })}

    ${createPagination(
      results.number ?? page,
      results.totalPages,
      total,
      baseUrl,
    )}
  `
}

/**
 * Fetch grant title from detail cache/API. Returns empty string on failure.
 * @param {string} bdnsCode
 * @returns {Promise<string>}
 */
async function fetchGrantTitle(bdnsCode) {
  try {
    const detail = await getGrantDetailCached(bdnsCode)
    return detail.descripcion || ''
  } catch {
    return ''
  }
}

/**
 * Parse beneficiary name — remove leading NIF/CIF if present.
 * @param {string} raw - Raw beneficiary string
 * @returns {string} Clean name
 */
function parseBeneficiaryName(raw) {
  if (!raw) return ''
  const match = raw.match(/^[A-Z]?\d{7,8}[A-Z]?\s*[-–—·]\s*(.+)$/i)
  if (match) return match[1].trim()
  return raw.trim()
}

/**
 * Create the page header with title and back link.
 * @param {Object} ctx - Header context
 * @returns {string} HTML
 */
function createHeader(ctx) {
  const { bdnsCode, nifCif, anio, returnTo, grantTitle, beneficiaryName } = ctx

  // Back link
  let backUrl, backLabel
  if (bdnsCode) {
    backUrl = `/ayuda/${encodeURIComponent(bdnsCode)}`
    backLabel = 'Volver a la ayuda'
  } else if (returnTo) {
    backUrl = returnTo
    backLabel = 'Volver a Transparencia'
  } else {
    const backParams = new URLSearchParams()
    if (anio) backParams.set('anio', anio)
    backUrl = `/transparencia${backParams.toString() ? '?' + backParams.toString() : ''}`
    backLabel = 'Volver a Transparencia'
  }

  // Title
  let title, subtitle
  if (bdnsCode) {
    title = 'Beneficiarios de esta ayuda'
    subtitle = grantTitle
      ? escapeHtml(grantTitle)
      : `Convocatoria BDNS ${escapeHtml(bdnsCode)}`
  } else {
    const displayName = beneficiaryName || nifCif
    title = `Concesiones de ${escapeHtml(displayName)}`
    subtitle = `NIF/CIF: ${escapeHtml(nifCif)}${anio ? ` · Ano ${anio}` : ' · Todos los anos'}`
  }

  return `
    <div class="mb-6">
      <a href="${backUrl}" data-link
         class="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-3 no-underline">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
        </svg>
        ${backLabel}
      </a>
      <h1 class="text-2xl font-bold text-gray-900 mb-1">${title}</h1>
      <p class="text-sm text-gray-500">${subtitle}</p>
    </div>
  `
}
