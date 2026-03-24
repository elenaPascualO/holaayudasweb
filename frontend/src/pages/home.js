/**
 * Homepage: search-first with semantic search + latest grants.
 */

import { getLatestGrants } from '../utils/api.js'
import { createSearchBar } from '../components/SearchBar.js'
import { createGrantList } from '../components/GrantList.js'
import { createPagination } from '../components/Pagination.js'
import { createEmptyState } from '../components/EmptyState.js'
import { formatNumber } from '../utils/formatters.js'

const EXAMPLE_SEARCHES = [
  { label: 'Digitalización pymes', query: 'ayudas digitalización pymes' },
  { label: 'Becas investigación', query: 'becas investigación universitaria' },
  { label: 'Vivienda joven', query: 'ayudas vivienda jovenes' },
  { label: 'Agricultura sostenible', query: 'subvenciones agricultura sostenible' },
  { label: 'Energías renovables', query: 'ayudas energía renovable' },
  { label: 'Empleo autónomos', query: 'ayudas empleo autónomos' },
]

/**
 * Render the homepage.
 * @param {Object} params - Query parameters (page)
 * @returns {Promise<string>} HTML
 */
export async function renderHomePage(params = {}) {
  const page = parseInt(params.page || '0', 10)

  let results
  try {
    results = await getLatestGrants(page, 20)
  } catch {
    return `
      ${createSearchBar()}
      ${createExampleChips()}
      ${createEmptyState(
        'Error al cargar',
        'No se pudieron cargar las ultimas ayudas. Intentalo de nuevo.'
      )}
    `
  }

  if (!results.content || results.content.length === 0) {
    return `
      ${createSearchBar()}
      ${createExampleChips()}
      ${createEmptyState()}
    `
  }

  return `
    <h1 class="text-2xl font-bold text-gray-900 mb-4">Busca ayudas y subvenciones públicas</h1>
    ${createSearchBar()}
    ${createExampleChips()}

    <div class="mt-6">
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
  `
}

/**
 * Create example search chips for semantic search.
 * @returns {string} HTML
 */
function createExampleChips() {
  return `
    <div class="mt-4 flex flex-wrap gap-2">
      <span class="text-xs text-gray-400 self-center mr-1">Prueba:</span>
      ${EXAMPLE_SEARCHES.map(({ label, query }) => `
        <button data-filter="${query}"
                class="px-3 py-1 rounded-full text-xs font-medium bg-primary/5 text-primary
                       hover:bg-primary/10 transition-colors cursor-pointer">
          ${label}
        </button>
      `).join('')}
    </div>
  `
}
