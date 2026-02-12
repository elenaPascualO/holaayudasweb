/**
 * Empty state / no results component.
 */

/**
 * Create an empty state message.
 * @param {string} title - Main message
 * @param {string} subtitle - Secondary message
 * @returns {string} HTML
 */
export function createEmptyState(
  title = 'No se encontraron resultados',
  subtitle = 'Prueba con otros terminos o ajusta los filtros'
) {
  return `
    <div class="text-center py-16">
      <div class="text-5xl mb-4">🔍</div>
      <p class="text-lg text-gray-500 font-medium">${title}</p>
      <p class="text-sm text-gray-400 mt-1">${subtitle}</p>
    </div>
  `
}
