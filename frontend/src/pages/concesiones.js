/**
 * Concesiones page — paginated list of concesiones for a beneficiary.
 */

import { searchConcesiones } from '../utils/api.js'
import { createConcessionList } from '../components/ConcessionCard.js'
import { createPagination } from '../components/Pagination.js'
import { createEmptyState } from '../components/EmptyState.js'
import { formatNumber, escapeHtml } from '../utils/formatters.js'

/**
 * Render the concesiones page.
 * @param {Object} params - Query parameters (nifCif, anio, page)
 * @returns {Promise<string>} HTML
 */
export async function renderConcesionesPage(params) {
  const nifCif = params.nifCif || ''
  const anio = params.anio || ''
  const page = parseInt(params.page || '0', 10)
  const pageSize = 20

  if (!nifCif) {
    return createEmptyState(
      'Falta el NIF/CIF',
      'Esta pagina necesita un parametro nifCif para buscar concesiones.'
    )
  }

  // Build search params
  const searchParams = { nifCif, page, pageSize }
  if (anio) {
    searchParams.fechaDesde = `${anio}-01-01`
    searchParams.fechaHasta = `${anio}-12-31`
  }

  let results
  try {
    results = await searchConcesiones(searchParams)
  } catch {
    return `
      ${createPageHeader(nifCif, anio)}
      ${createEmptyState(
        'Error al cargar',
        'No se pudo conectar con el servidor. Intentalo de nuevo.'
      )}
    `
  }

  const items = results.content || []
  if (items.length === 0) {
    return `
      ${createPageHeader(nifCif, anio)}
      ${createEmptyState(
        'Sin concesiones',
        `No se encontraron concesiones para ${escapeHtml(nifCif)}${anio ? ` en ${anio}` : ''}.`
      )}
    `
  }

  // Extract beneficiary name from first result
  const rawName = items[0].beneficiario || items[0].denominacion || nifCif
  const name = parseBeneficiaryName(rawName)

  const total = results.totalElements || items.length

  // Build base URL for pagination
  const baseParams = new URLSearchParams()
  baseParams.set('nifCif', nifCif)
  if (anio) baseParams.set('anio', anio)
  const baseUrl = `/concesiones?${baseParams.toString()}`

  return `
    ${createPageHeader(nifCif, anio, name)}

    <p class="text-sm text-gray-400 mb-4">
      ${formatNumber(total)} concesion${total !== 1 ? 'es' : ''}${anio ? ` en ${anio}` : ''}
    </p>

    ${createConcessionList(items, { showConvocatoria: true })}

    ${createPagination(
      results.number ?? page,
      results.totalPages,
      total,
      baseUrl,
    )}
  `
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
 * @param {string} nifCif - NIF/CIF
 * @param {string} anio - Year filter
 * @param {string} [name] - Beneficiary name
 * @returns {string} HTML
 */
function createPageHeader(nifCif, anio, name = '') {
  const displayName = name || nifCif
  // Build back link to transparencia preserving year
  const backParams = new URLSearchParams()
  if (anio) backParams.set('anio', anio)
  const backUrl = `/transparencia${backParams.toString() ? '?' + backParams.toString() : ''}`

  return `
    <div class="mb-6">
      <a href="${backUrl}" data-link
         class="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-3 no-underline">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
        </svg>
        Volver a Transparencia
      </a>
      <h1 class="text-2xl font-bold text-gray-900 mb-1">
        Concesiones de ${escapeHtml(displayName)}
      </h1>
      <p class="text-sm text-gray-500">
        NIF/CIF: ${escapeHtml(nifCif)}${anio ? ` · Año ${anio}` : ' · Todos los años'}
      </p>
    </div>
  `
}
