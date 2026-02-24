/**
 * Homepage: latest grants with filters and pagination.
 */

import { getLatestGrants } from '../utils/api.js'
import { COMMUNITIES, PROVINCES } from '../utils/regionCache.js'
import { getCatalogs } from '../utils/catalogCache.js'
import { createSearchBar, createQuickFilters } from '../components/SearchBar.js'
import { createGrantList } from '../components/GrantList.js'
import { createFilterPanel } from '../components/FilterPanel.js'
import { createPagination } from '../components/Pagination.js'
import { createEmptyState } from '../components/EmptyState.js'
import { formatNumber } from '../utils/formatters.js'

/**
 * Render the homepage.
 * @param {Object} params - Query parameters (page)
 * @returns {Promise<string>} HTML
 */
export async function renderHomePage(params = {}) {
  const page = parseInt(params.page || '0', 10)

  const catalogs = await getCatalogs()

  let results
  try {
    results = await getLatestGrants(page, 20)
  } catch {
    return `
      ${createSearchBar()}
      ${createQuickFilters()}
      ${createEmptyState(
        'Error al cargar',
        'No se pudieron cargar las ultimas ayudas. Intentalo de nuevo.'
      )}
    `
  }

  if (!results.content || results.content.length === 0) {
    return `
      ${createSearchBar()}
      ${createQuickFilters()}
      ${createEmptyState()}
    `
  }

  return `
    ${createSearchBar()}
    ${createQuickFilters()}

    <div class="mt-6 flex flex-col md:flex-row gap-6">
      <aside class="md:w-60 shrink-0 order-2 md:order-1">
        ${createFilterPanel({}, { communities: COMMUNITIES, provinces: PROVINCES }, catalogs)}
      </aside>

      <div class="flex-1 order-1 md:order-2">
        <div class="flex items-center justify-between mb-4">
          <p class="text-sm text-gray-400">
            ${formatNumber(results.totalElements)} ayudas publicadas
          </p>
        </div>

        ${createGrantList(results.content)}

        ${createPagination(
          results.number,
          results.totalPages,
          results.totalElements,
          '/',
        )}
      </div>
    </div>
  `
}
