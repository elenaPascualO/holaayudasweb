/**
 * Search results page with filters and pagination.
 */

import { searchGrants } from '../utils/api.js'
import { COMMUNITIES, PROVINCES } from '../utils/regionCache.js'
import { createSearchBar } from '../components/SearchBar.js'
import { createGrantList } from '../components/GrantList.js'
import { createFilterPanel } from '../components/FilterPanel.js'
import { createPagination } from '../components/Pagination.js'
import { createEmptyState } from '../components/EmptyState.js'
import { formatNumber } from '../utils/formatters.js'

/**
 * Render the search results page.
 * @param {Object} params - Query parameters (q, page, pageSize, etc.)
 * @returns {Promise<string>} HTML
 */
export async function renderSearchPage(params) {
  const q = params.q || ''
  const page = parseInt(params.page || '0', 10)
  const pageSize = parseInt(params.pageSize || '20', 10)

  // Default fechaDesde to 1st of current month
  const now = new Date()
  const defaultFechaDesde = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
  const fechaDesde = params.fechaDesde ?? defaultFechaDesde

  let results
  try {
    results = await searchGrants({
      q,
      page,
      pageSize,
      fechaDesde,
      fechaHasta: params.fechaHasta,
      tipoAdministracion: params.tipoAdministracion,
      regiones: params.regiones,
      orden: params.orden,
      estado: params.estado,
    })
  } catch {
    return `
      ${createSearchBar(q)}
      ${createEmptyState(
        'Error al buscar',
        'No se pudo conectar con el servidor. Intentalo de nuevo.'
      )}
    `
  }

  if (!results.content || results.content.length === 0) {
    return `
      ${createSearchBar(q)}
      ${createEmptyState()}
    `
  }

  // Build base URL for pagination (preserving all filters)
  const baseParams = new URLSearchParams()
  if (q) baseParams.set('q', q)
  if (fechaDesde) baseParams.set('fechaDesde', fechaDesde)
  if (params.fechaHasta) baseParams.set('fechaHasta', params.fechaHasta)
  if (params.tipoAdministracion) baseParams.set('tipoAdministracion', params.tipoAdministracion)
  if (params.regiones) baseParams.set('regiones', params.regiones)
  if (params.orden) baseParams.set('orden', params.orden)
  if (params.estado) baseParams.set('estado', params.estado)
  const baseUrl = `/buscar?${baseParams.toString()}`

  return `
    <a href="/" data-link class="inline-flex items-center gap-1 text-sm text-gray-400 hover:text-gray-700 transition-colors mb-4">
      <span>&#8592;</span> Inicio
    </a>

    ${createSearchBar(q)}

    <div class="mt-6 flex flex-col md:flex-row gap-6">
      <aside class="md:w-60 shrink-0 order-2 md:order-1">
        ${createFilterPanel({ ...params, fechaDesde }, { communities: COMMUNITIES, provinces: PROVINCES })}
      </aside>

      <div class="flex-1 order-1 md:order-2">
        <div class="flex items-center justify-between mb-4">
          <p class="text-sm text-gray-400">
            ${formatNumber(results.totalElements)} resultados
            ${q ? ` para "${q}"` : ''}
          </p>
          <select
            id="sort-select"
            class="text-sm text-gray-500 border border-gray-200 rounded-lg px-2 py-1
                   focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
          >
            <option value="desc" ${(params.orden || 'desc') === 'desc' ? 'selected' : ''}>Mas recientes</option>
            <option value="asc" ${params.orden === 'asc' ? 'selected' : ''}>Mas antiguas</option>
          </select>
        </div>

        ${createGrantList(results.content)}

        ${createPagination(
          results.number,
          results.totalPages,
          results.totalElements,
          baseUrl,
        )}
      </div>
    </div>
  `
}
