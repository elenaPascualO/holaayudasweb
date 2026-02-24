/**
 * Pagination controls.
 */

import { formatNumber } from '../utils/formatters.js'

/**
 * Create pagination controls.
 * @param {number} currentPage - Current page (0-indexed)
 * @param {number} totalPages - Total number of pages
 * @param {number} totalElements - Total number of results
 * @param {string} baseUrl - Base URL for pagination links (e.g., "/buscar?q=test")
 * @returns {string} HTML
 */
export function createPagination(currentPage, totalPages, totalElements, baseUrl) {
  if (totalPages <= 1) return ''

  const prevDisabled = currentPage === 0
  const nextDisabled = currentPage >= totalPages - 1

  // Build URLs preserving existing query params
  const sep = baseUrl.includes('?') ? '&' : '?'
  const prevUrl = prevDisabled ? '#' : `${baseUrl}${sep}page=${currentPage - 1}`
  const nextUrl = nextDisabled ? '#' : `${baseUrl}${sep}page=${currentPage + 1}`

  return `
    <nav class="flex items-center justify-between mt-6 pt-4 border-t border-gray-100" aria-label="Paginacion">
      <button
        ${prevDisabled ? 'disabled' : `data-link="${prevUrl}"`}
        class="flex items-center gap-1 px-4 py-2 text-sm font-medium rounded-lg
               ${prevDisabled
                 ? 'text-gray-300 cursor-not-allowed'
                 : 'text-gray-600 hover:bg-gray-50 hover:text-primary cursor-pointer'}"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
        </svg>
        Anterior
      </button>

      <span class="text-sm text-gray-500">
        Pagina <strong>${currentPage + 1}</strong> de <strong>${formatNumber(totalPages)}</strong>
        <span class="hidden sm:inline text-gray-400">
          · ${formatNumber(totalElements)} resultados
        </span>
      </span>

      <button
        ${nextDisabled ? 'disabled' : `data-link="${nextUrl}"`}
        class="flex items-center gap-1 px-4 py-2 text-sm font-medium rounded-lg
               ${nextDisabled
                 ? 'text-gray-300 cursor-not-allowed'
                 : 'text-gray-600 hover:bg-gray-50 hover:text-primary cursor-pointer'}"
      >
        Siguiente
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
        </svg>
      </button>
    </nav>
  `
}
