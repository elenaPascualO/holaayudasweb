/**
 * Search input and quick filter chips.
 */

import { escapeHtml } from '../utils/formatters.js'

const QUICK_FILTERS = [
  { label: 'Autonomos', query: 'autonomos' },
  { label: 'PYMEs', query: 'pyme pequena empresa' },
  { label: 'Educacion', query: 'educacion formacion' },
  { label: 'Cultura', query: 'cultura artes' },
  { label: 'I+D', query: 'investigacion desarrollo innovacion' },
  { label: 'Empleo', query: 'empleo contratacion' },
  { label: 'Digitalizacion', query: 'digitalizacion tecnologia' },
  { label: 'Agricultura', query: 'agricultura ganaderia' },
]

/**
 * Create the main search bar.
 * @param {string} currentQuery - Current search text to pre-fill
 * @returns {string} HTML
 */
export function createSearchBar(currentQuery = '') {
  return `
    <form id="search-form" class="w-full max-w-2xl mx-auto">
      <div class="relative">
        <input
          id="search-input"
          type="text"
          value="${escapeHtml(currentQuery)}"
          placeholder="Busca ayudas por texto, tema o codigo BDNS..."
          class="w-full px-5 py-3.5 pr-14 rounded-xl border border-gray-200 bg-white text-gray-900
                 placeholder-gray-400 text-base
                 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary
                 shadow-sm transition-shadow focus:shadow-md"
        />
        <button
          type="submit"
          class="absolute right-2 top-1/2 -translate-y-1/2 p-2.5 rounded-lg
                 bg-primary text-white hover:bg-primary-dark transition-colors"
          aria-label="Buscar"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
        </button>
      </div>
    </form>
  `
}

/**
 * Create quick filter chips.
 * @returns {string} HTML
 */
export function createQuickFilters() {
  const chips = QUICK_FILTERS.map(
    (f) => `
      <button
        data-filter="${escapeHtml(f.query)}"
        class="px-3 py-1.5 rounded-full text-sm font-medium
               bg-gray-100 text-gray-600 hover:bg-primary/10 hover:text-primary
               transition-colors whitespace-nowrap"
      >
        ${escapeHtml(f.label)}
      </button>
    `
  ).join('')

  return `
    <div class="flex flex-wrap justify-center gap-2 mt-4">
      ${chips}
    </div>
  `
}
