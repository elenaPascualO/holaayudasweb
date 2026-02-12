/**
 * Homepage: search hero + latest grants feed.
 */

import { getLatestGrants } from '../utils/api.js'
import { createSearchBar, createQuickFilters } from '../components/SearchBar.js'
import { createGrantList } from '../components/GrantList.js'
import { formatNumber } from '../utils/formatters.js'

/**
 * Render the homepage.
 * @returns {Promise<string>} HTML
 */
export async function renderHomePage() {
  let latestHtml = ''

  try {
    const latest = await getLatestGrants(0, 10)
    latestHtml = createGrantList(latest.content)
  } catch {
    latestHtml = `
      <div class="text-center py-8">
        <p class="text-gray-400 text-sm">No se pudieron cargar las ultimas ayudas</p>
      </div>
    `
  }

  return `
    <section class="py-10 text-center">
      <h1 class="text-3xl sm:text-4xl font-bold text-gray-900 mb-2">
        Encuentra tu ayuda
      </h1>
      <p class="text-gray-500 mb-8 max-w-lg mx-auto">
        Busca entre mas de ${formatNumber(600000)} ayudas y subvenciones publicas
        de forma facil y rapida
      </p>
      ${createSearchBar()}
      ${createQuickFilters()}
    </section>

    <section class="mt-10">
      <h2 class="text-lg font-semibold text-gray-700 mb-4">
        Ultimas ayudas publicadas
      </h2>
      ${latestHtml}
    </section>
  `
}
