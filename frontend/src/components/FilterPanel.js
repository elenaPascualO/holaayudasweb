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
 * @returns {string} HTML
 */
export function createFilterPanel(currentFilters = {}) {
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
        </fieldset>

        <!-- Date range -->
        <fieldset>
          <legend class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Fecha de publicacion
          </legend>
          <div class="space-y-2">
            <div>
              <label class="text-xs text-gray-400" for="fechaDesde">Desde</label>
              <input
                type="date"
                id="fechaDesde"
                name="fechaDesde"
                value="${escapeHtml(currentFilters.fechaDesde || '')}"
                class="w-full mt-0.5 px-3 py-1.5 text-sm border border-gray-200 rounded-lg
                       focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
              />
            </div>
            <div>
              <label class="text-xs text-gray-400" for="fechaHasta">Hasta</label>
              <input
                type="date"
                id="fechaHasta"
                name="fechaHasta"
                value="${escapeHtml(currentFilters.fechaHasta || '')}"
                class="w-full mt-0.5 px-3 py-1.5 text-sm border border-gray-200 rounded-lg
                       focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
              />
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

/**
 * Check if there are any active filters.
 * @param {Object} filters
 * @returns {boolean}
 */
function hasActiveFilters(filters) {
  return !!(filters.tipoAdministracion || filters.fechaDesde || filters.fechaHasta || filters.regiones)
}
