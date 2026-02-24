/**
 * Transparencia page — ranking of top public money beneficiaries.
 */

import { searchTopBeneficiaries, getTopBeneficiariesYears } from '../utils/api.js'
import { createBeneficiaryList } from '../components/BeneficiaryRow.js'
import { createPagination } from '../components/Pagination.js'
import { createEmptyState } from '../components/EmptyState.js'
import { formatNumber } from '../utils/formatters.js'

/**
 * Render the transparencia page.
 * @param {Object} params - Query parameters (anio, nifCif, q, page)
 * @returns {Promise<string>} HTML
 */
export async function renderTransparenciaPage(params) {
  const page = parseInt(params.page || '0', 10)
  const pageSize = 20

  // Load years for the dropdown
  // API returns [{id: 2024, descripcion: 2024}, ...] — extract numeric values
  let years = []
  try {
    const rawYears = await getTopBeneficiariesYears()
    if (Array.isArray(rawYears)) {
      years = rawYears.map((y) => (typeof y === 'object' ? y.id || y.descripcion : y))
      years.sort((a, b) => b - a)
    }
  } catch {
    years = []
  }

  // "todos" = user explicitly chose all years; undefined = first visit (default to latest)
  const anio = params.anio === 'todos' ? null
    : params.anio ? parseInt(params.anio, 10)
    : (years[0] || null)
  const nifCif = params.nifCif || ''
  const q = params.q || ''

  // Build search params
  const searchParams = { page, pageSize }
  if (anio) searchParams.anio = anio
  if (nifCif) searchParams.nifCif = nifCif
  if (q) searchParams.q = q

  let results
  try {
    results = await searchTopBeneficiaries(searchParams)
  } catch {
    return `
      ${createPageHeader(years, anio, nifCif, q)}
      ${createEmptyState(
        'Error al cargar',
        'No se pudo conectar con el servidor. Intentalo de nuevo.'
      )}
    `
  }

  if (!results.content || results.content.length === 0) {
    const emptyMsg = q
      ? `No se encontraron grandes beneficiarios con el nombre "${escapeAttr(q)}".`
      : nifCif
        ? `No se encontraron grandes beneficiarios con NIF/CIF "${nifCif}".`
        : 'No hay datos de grandes beneficiarios para el periodo seleccionado.'
    return `
      ${createPageHeader(years, anio, nifCif, q)}
      ${createEmptyState('Sin resultados', emptyMsg)}
    `
  }

  const startRank = page * pageSize + 1

  // On page 0, compute the global max from the #1 beneficiary.
  // On subsequent pages, read it from the URL param so bars stay proportional.
  const pageMax = Math.max(...results.content.map((i) => i.ayudaETotal || 0))
  const globalMax = page === 0 ? pageMax : (params.maxImporte ? parseFloat(params.maxImporte) : pageMax)

  // Build base URL for pagination (include maxImporte for consistent bars)
  const baseParams = new URLSearchParams()
  if (anio) baseParams.set('anio', anio)
  if (nifCif) baseParams.set('nifCif', nifCif)
  if (q) baseParams.set('q', q)
  const maxForUrl = page === 0 ? pageMax : globalMax
  baseParams.set('maxImporte', maxForUrl)
  const baseUrl = `/transparencia?${baseParams.toString()}`

  return `
    ${createPageHeader(years, anio, nifCif, q)}

    <p class="text-sm text-gray-400 mb-4">
      ${formatNumber(results.totalElements)} grandes beneficiarios${anio ? ` en ${anio}` : ''}
    </p>

    <div id="beneficiarios-ranking" data-anio="${anio || ''}">
    ${createBeneficiaryList(results.content, startRank, globalMax)}
    </div>

    ${createPagination(
      results.number ?? page,
      results.totalPages,
      results.totalElements,
      baseUrl,
    )}
  `
}

/**
 * Create the page header with title, description, and filters.
 * @param {Array} years - Available years
 * @param {number|null} selectedYear - Currently selected year
 * @param {string} nifCif - Current NIF/CIF filter
 * @param {string} searchQuery - Current text search query
 * @returns {string} HTML
 */
function createPageHeader(years, selectedYear, nifCif, searchQuery = '') {
  return `
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900 mb-1">Transparencia</h1>
      <p class="text-sm text-gray-500">
        Ranking de los mayores receptores de dinero publico en España.
        Datos en tiempo real de la
        <a href="https://www.infosubvenciones.es/bdnstrans/GE/es/grandesbeneficiarios"
           target="_blank" rel="noopener noreferrer"
           class="text-primary hover:underline">BDNS</a>.
      </p>
      <p class="text-xs text-gray-400 mt-1">
        La BDNS solo publica datos de grandes beneficiarios desde 2022.
      </p>
    </div>

    <form id="transparencia-filters" class="flex flex-wrap items-end gap-3 mb-6">
      <div>
        <label for="nombre-input" class="block text-xs font-medium text-gray-500 mb-1">Buscar por nombre</label>
        <input
          type="text"
          id="nombre-input"
          name="q"
          value="${escapeAttr(searchQuery)}"
          placeholder="Ej: Iberdrola, Telefonica..."
          class="text-sm border border-gray-200 rounded-lg px-3 py-2 w-52
                 focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
        />
      </div>

      <div>
        <label for="anio-select" class="block text-xs font-medium text-gray-500 mb-1">Año</label>
        <select
          id="anio-select"
          name="anio"
          class="text-sm border border-gray-200 rounded-lg px-3 py-2
                 focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
        >
          <option value="" ${selectedYear === null ? 'selected' : ''}>Todos</option>
          ${years.map((y) => `
            <option value="${y}" ${y === selectedYear ? 'selected' : ''}>${y}</option>
          `).join('')}
        </select>
      </div>

      <div>
        <label for="nifcif-input" class="block text-xs font-medium text-gray-500 mb-1">NIF/CIF</label>
        <input
          type="text"
          id="nifcif-input"
          name="nifCif"
          value="${escapeAttr(nifCif)}"
          placeholder="Ej: A07129430"
          class="text-sm border border-gray-200 rounded-lg px-3 py-2 w-40
                 focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
        />
      </div>

      <button
        type="submit"
        class="px-4 py-2 text-sm font-medium bg-primary text-white rounded-lg
               hover:bg-primary-dark transition-colors cursor-pointer"
      >
        Filtrar
      </button>
    </form>
  `
}

/**
 * Escape a string for use in HTML attributes.
 * @param {string} str
 * @returns {string}
 */
function escapeAttr(str) {
  if (!str) return ''
  return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
