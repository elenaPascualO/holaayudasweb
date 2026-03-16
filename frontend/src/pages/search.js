/**
 * Search results page with semantic search and simplified filters.
 */

import { semanticSearch, searchGrants } from '../utils/api.js'
import { createSearchBar, createQuickFilters } from '../components/SearchBar.js'
import { createGrantList } from '../components/GrantList.js'
import { createSemanticFilterPanel } from '../components/FilterPanel.js'
import { createPagination } from '../components/Pagination.js'
import { createEmptyState } from '../components/EmptyState.js'
import { formatNumber } from '../utils/formatters.js'

/**
 * Create a back link to return to analytics when navigated from there.
 * @param {string|undefined} returnTo - URL to return to
 * @returns {string} HTML (empty if no returnTo)
 */
function createBackLink(returnTo) {
  if (!returnTo) return ''
  return `<a href="${returnTo}" data-link
     class="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-3 no-underline">
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
    </svg>
    Volver a Estadisticas
  </a>`
}

/**
 * Render the search results page.
 * @param {Object} params - Query parameters (q, page, pageSize, etc.)
 * @returns {Promise<string>} HTML
 */
export async function renderSearchPage(params) {
  const q = params.q || ''
  const page = parseInt(params.page || '0', 10)
  const pageSize = parseInt(params.pageSize || '20', 10)

  // Determine if we should use semantic search or legacy BDNS search
  const useSemanticSearch = !!q

  // Map estado (abiertas/cerradas) to abierto (true/false) for the filter panel
  let abierto = params.abierto
  if (!abierto && params.estado) {
    abierto = params.estado === 'abiertas' ? 'true' : params.estado === 'cerradas' ? 'false' : ''
  }

  const currentFilters = {
    yearFrom: params.yearFrom,
    yearTo: params.yearTo,
    abierto,
  }

  let results
  try {
    if (useSemanticSearch) {
      // Fetch full pool WITHOUT filters — filters and pagination applied client-side
      // to preserve semantic relevance ordering
      const rawResults = await semanticSearch({ q, topK: 200 })
      results = applySemanticFilters(rawResults, {
        abierto,
        yearFrom: params.yearFrom,
        yearTo: params.yearTo,
      }, page, pageSize)
    } else {
      // No query — fall back to legacy BDNS search for browsing
      // Skip default date filter when analytics drill-down filters are present
      const hasAnalyticsFilter = params.descripcionFinalidad || params.regionDesc || params.estado
      const hasYearFilter = params.yearFrom || params.yearTo
      const now = new Date()
      const defaultFechaDesde = (hasAnalyticsFilter || hasYearFilter)
        ? undefined
        : `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
      // Convert yearFrom/yearTo to fechaDesde/fechaHasta when present
      const fechaDesde = params.fechaDesde
        ?? (params.yearFrom ? `${params.yearFrom}-01-01` : defaultFechaDesde)
      const fechaHasta = params.fechaHasta
        ?? (params.yearTo ? `${params.yearTo}-12-31` : undefined)

      results = await searchGrants({
        q: '',
        page,
        pageSize,
        fechaDesde,
        fechaHasta,
        tipoAdministracion: params.tipoAdministracion,
        regiones: params.regiones,
        orden: params.orden,
        estado: params.estado,
        instrumentos: params.instrumentos,
        tiposBeneficiario: params.tiposBeneficiario,
        finalidad: params.finalidad,
        descripcionFinalidad: params.descripcionFinalidad,
        regionDesc: params.regionDesc,
      })
    }
  } catch {
    return `
      ${createBackLink(params.returnTo)}
      ${createSearchBar(q)}
      ${createQuickFilters()}

      <div class="mt-6">
        ${createSemanticFilterPanel(currentFilters)}
        <div class="mt-4">
          ${createEmptyState(
            'Error al buscar',
            'No se pudo conectar con el servidor. Intentalo de nuevo.'
          )}
        </div>
      </div>
    `
  }

  if (!results.content || results.content.length === 0) {
    return `
      ${createBackLink(params.returnTo)}
      ${createSearchBar(q)}
      ${createQuickFilters()}

      <div class="mt-6">
        ${createSemanticFilterPanel(currentFilters)}
        <div class="mt-4">
          ${createEmptyState(
            q ? 'Sin resultados' : undefined,
            q ? `No se encontraron ayudas para "${q}". Prueba con otros terminos.` : undefined,
          )}
        </div>
      </div>
    `
  }

  // Build base URL for pagination (preserving filters)
  const baseParams = new URLSearchParams()
  if (q) baseParams.set('q', q)
  if (params.yearFrom) baseParams.set('yearFrom', params.yearFrom)
  if (params.yearTo) baseParams.set('yearTo', params.yearTo)
  if (params.abierto) baseParams.set('abierto', params.abierto)
  // Legacy filter params (for non-semantic search)
  if (!useSemanticSearch) {
    if (params.fechaDesde) baseParams.set('fechaDesde', params.fechaDesde)
    if (params.fechaHasta) baseParams.set('fechaHasta', params.fechaHasta)
    if (params.tipoAdministracion) baseParams.set('tipoAdministracion', params.tipoAdministracion)
    if (params.regiones) baseParams.set('regiones', params.regiones)
    if (params.orden) baseParams.set('orden', params.orden)
    if (params.estado) baseParams.set('estado', params.estado)
    if (params.descripcionFinalidad) baseParams.set('descripcionFinalidad', params.descripcionFinalidad)
    if (params.regionDesc) baseParams.set('regionDesc', params.regionDesc)
  }
  if (params.returnTo) baseParams.set('returnTo', params.returnTo)
  const baseUrl = `/buscar?${baseParams.toString()}`

  // Check if results have relevance scores
  const hasScores = results.content.some(r => r._score != null)

  return `
    ${createBackLink(params.returnTo)}
    ${createSearchBar(q)}
    ${createQuickFilters()}

    <div class="mt-6">
      ${createSemanticFilterPanel(currentFilters)}

      <div class="mt-4">
        <div class="flex items-center justify-between mb-4">
          <p class="text-sm text-gray-400">
            ${formatNumber(results.totalElements)} resultados
            ${q ? ` para "${q}"` : ''}
            ${params.descripcionFinalidad ? ` de "${params.descripcionFinalidad}"` : ''}
            ${params.regionDesc ? ` en "${params.regionDesc}"` : ''}
            ${params.estado ? ` (${params.estado})` : ''}
            ${hasScores ? ' <span class="text-primary/60">· ordenados por relevancia</span>' : ''}
          </p>
          ${!useSemanticSearch ? `
            <select
              id="sort-select"
              class="text-sm text-gray-500 border border-gray-200 rounded-lg px-2 py-1
                     focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
            >
              <option value="desc" ${(params.orden || 'desc') === 'desc' ? 'selected' : ''}>Mas recientes</option>
              <option value="asc" ${params.orden === 'asc' ? 'selected' : ''}>Mas antiguas</option>
            </select>
          ` : ''}
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

/**
 * Apply year/status filters and pagination client-side to semantic search results.
 * Filters use _status (date-based, what user sees) not raw abierto flag.
 * @param {Object} rawResults - API response from semantic search
 * @param {Object} filters - { abierto, yearFrom, yearTo }
 * @param {number} page - Current page (0-indexed)
 * @param {number} pageSize - Results per page
 * @returns {Object} Filtered and paginated results in same format
 */
function applySemanticFilters(rawResults, filters, page, pageSize) {
  if (!rawResults.content) return rawResults

  let filtered = rawResults.content

  // Status filter: "Abiertas" excludes only confirmed-closed items
  // (keeps open, permanent, and unknown — unknown shouldn't be treated as closed)
  if (filters.abierto === 'true') {
    filtered = filtered.filter(r => r._status !== 'closed')
  } else if (filters.abierto === 'false') {
    filtered = filtered.filter(r => r._status === 'closed')
  }

  // Year range filters
  if (filters.yearFrom) {
    filtered = filtered.filter(r => (r.fechaRecepcion || '') >= `${filters.yearFrom}-01-01`)
  }
  if (filters.yearTo) {
    filtered = filtered.filter(r => (r.fechaRecepcion || '') <= `${filters.yearTo}-12-31`)
  }

  const totalPages = Math.ceil(filtered.length / pageSize) || 1
  const safePage = Math.min(page, totalPages - 1)
  const start = safePage * pageSize
  const sliced = filtered.slice(start, start + pageSize)

  return {
    ...rawResults,
    content: sliced,
    totalElements: filtered.length,
    totalPages,
    number: safePage,
  }
}
