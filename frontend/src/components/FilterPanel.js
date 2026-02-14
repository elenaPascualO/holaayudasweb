/**
 * Search filter panel (sidebar on desktop, collapsible on mobile).
 */

import { escapeHtml } from '../utils/formatters.js'

const ADMIN_TYPES = [
  { value: '', label: 'Todas' },
  { value: 'C', label: 'Central' },
  { value: 'A', label: 'Autonomica' },
  { value: 'L', label: 'Local' },
  { value: 'O', label: 'Otros' },
]

/**
 * Create the filter panel.
 * @param {Object} currentFilters - Currently active filter values
 * @param {Object} regionData - Region lists for dropdowns
 * @param {Array<{id: number, name: string}>} [regionData.communities]
 * @param {Array<{id: number, name: string}>} [regionData.provinces]
 * @returns {string} HTML
 */
export function createFilterPanel(currentFilters = {}, regionData = {}) {
  return `
    <div class="bg-white rounded-xl border border-gray-100 p-4">
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-semibold text-gray-900 text-sm">Filtros</h3>
        ${hasActiveFilters(currentFilters) ? `
          <button
            id="clear-filters"
            class="text-xs text-primary hover:underline cursor-pointer"
          >
            Limpiar
          </button>
        ` : ''}
      </div>

      <form id="filter-form" class="space-y-5">
        <!-- Admin type -->
        <fieldset>
          <legend class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Administracion
          </legend>
          <div class="space-y-1.5">
            ${ADMIN_TYPES.map((t) => `
              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="tipoAdministracion"
                  value="${t.value}"
                  ${(currentFilters.tipoAdministracion || '') === t.value ? 'checked' : ''}
                  class="accent-primary"
                />
                <span class="text-sm text-gray-700">${t.label}</span>
              </label>
            `).join('')}
          </div>

          ${createRegionSelect(
            'region-communities',
            'region-communities-wrapper',
            'Comunidad autonoma',
            regionData.communities || [],
            currentFilters.regiones,
            currentFilters.tipoAdministracion === 'A',
          )}

          ${createRegionSelect(
            'region-provinces',
            'region-provinces-wrapper',
            'Provincia',
            regionData.provinces || [],
            currentFilters.regiones,
            currentFilters.tipoAdministracion === 'L',
          )}
        </fieldset>

        <!-- Date range -->
        <fieldset>
          <legend class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Fecha de publicacion
          </legend>
          <div class="space-y-2">
            <div>
              <label class="text-xs text-gray-400">Desde</label>
              <div class="flex gap-1.5 mt-0.5">
                ${createYearSelect('fechaDesdeYear', currentFilters.fechaDesde)}
                ${createMonthSelect('fechaDesdeMonth', currentFilters.fechaDesde)}
              </div>
            </div>
            <div>
              <label class="text-xs text-gray-400">Hasta</label>
              <div class="flex gap-1.5 mt-0.5">
                ${createYearSelect('fechaHastaYear', currentFilters.fechaHasta)}
                ${createMonthSelect('fechaHastaMonth', currentFilters.fechaHasta)}
              </div>
            </div>
          </div>
        </fieldset>

        <button
          type="submit"
          class="w-full py-2 text-sm font-medium text-white bg-primary rounded-lg
                 hover:bg-primary-dark transition-colors cursor-pointer"
        >
          Aplicar filtros
        </button>
      </form>
    </div>
  `
}

const MONTH_NAMES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

const FIRST_YEAR = 2003

/**
 * Extract year from a YYYY-MM-DD date string.
 * @param {string} dateStr
 * @returns {string}
 */
function extractYear(dateStr) {
  if (!dateStr) return ''
  return dateStr.split('-')[0] || ''
}

/**
 * Extract month (1-indexed) from a YYYY-MM-DD date string.
 * @param {string} dateStr
 * @returns {string}
 */
function extractMonth(dateStr) {
  if (!dateStr) return ''
  const parts = dateStr.split('-')
  return parts[1] ? String(parseInt(parts[1], 10)) : ''
}

/**
 * Create a year <select> dropdown (current year down to FIRST_YEAR).
 * @param {string} id - Element id
 * @param {string} dateStr - Current YYYY-MM-DD value to pre-select
 * @returns {string} HTML
 */
function createYearSelect(id, dateStr) {
  const currentYear = new Date().getFullYear()
  const selected = extractYear(dateStr)
  let options = '<option value="">Año</option>'
  for (let y = currentYear; y >= FIRST_YEAR; y--) {
    options += `<option value="${y}" ${String(y) === selected ? 'selected' : ''}>${y}</option>`
  }
  return `
    <select
      id="${id}"
      name="${id}"
      class="flex-1 min-w-0 px-2 py-1.5 text-sm border border-gray-200 rounded-lg
             focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
    >${options}</select>
  `
}

/**
 * Create a month <select> dropdown.
 * @param {string} id - Element id
 * @param {string} dateStr - Current YYYY-MM-DD value to pre-select
 * @returns {string} HTML
 */
function createMonthSelect(id, dateStr) {
  const selected = extractMonth(dateStr)
  let options = '<option value="">Mes</option>'
  MONTH_NAMES.forEach((name, i) => {
    const val = i + 1
    options += `<option value="${val}" ${String(val) === selected ? 'selected' : ''}>${name}</option>`
  })
  return `
    <select
      id="${id}"
      name="${id}"
      class="flex-1 min-w-0 px-2 py-1.5 text-sm border border-gray-200 rounded-lg
             focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
    >${options}</select>
  `
}

/**
 * Check if there are any active filters.
 * @param {Object} filters
 * @returns {boolean}
 */
function hasActiveFilters(filters) {
  return !!(filters.tipoAdministracion || filters.fechaDesde || filters.fechaHasta || filters.regiones)
}

/**
 * Create a region select dropdown.
 * @param {string} id - Element id for the select
 * @param {string} wrapperId - Element id for the wrapper div
 * @param {string} label - Placeholder label
 * @param {Array<{id: number, name: string}>} options - Region options
 * @param {string} selectedValue - Currently selected region id
 * @param {boolean} visible - Whether to show the dropdown
 * @returns {string} HTML
 */
function createRegionSelect(id, wrapperId, label, options, selectedValue, visible) {
  if (options.length === 0) return `<div id="${wrapperId}" class="hidden"></div>`
  return `
    <div id="${wrapperId}" class="${visible ? 'mt-2' : 'hidden mt-2'}">
      <select
        id="${id}"
        class="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-lg
               focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
      >
        <option value="">${escapeHtml(label)}</option>
        ${options.map((r) => `
          <option value="${r.id}" ${String(r.id) === String(selectedValue) ? 'selected' : ''}>
            ${escapeHtml(r.name)}
          </option>
        `).join('')}
      </select>
    </div>
  `
}
