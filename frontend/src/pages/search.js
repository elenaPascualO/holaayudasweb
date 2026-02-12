/**
 * Search results page with filters and pagination.
 */

import { searchGrants } from '../utils/api.js'
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

  let results
  try {
    results = await searchGrants({
      q,
      page,
      pageSize,
      fechaDesde: params.fechaDesde,
      fechaHasta: params.fechaHasta,
      tipoAdministracion: params.tipoAdministracion,
      regiones: params.regiones,
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
  if (params.fechaDesde) baseParams.set('fechaDesde', params.fechaDesde)
  if (params.fechaHasta) baseParams.set('fechaHasta', params.fechaHasta)
  if (params.tipoAdministracion) baseParams.set('tipoAdministracion', params.tipoAdministracion)
  if (params.regiones) baseParams.set('regiones', params.regiones)
  const baseUrl = `/buscar?${baseParams.toString()}`

  return `
    ${createSearchBar(q)}

    <div class="mt-6 flex flex-col md:flex-row gap-6">
      <aside class="md:w-60 shrink-0 order-2 md:order-1">
        ${createFilterPanel(params)}
      </aside>

      <div class="flex-1 order-1 md:order-2">
        <p class="text-sm text-gray-400 mb-4">
          ${formatNumber(results.totalElements)} resultados
          ${q ? ` para "${q}"` : ''}
        </p>

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
