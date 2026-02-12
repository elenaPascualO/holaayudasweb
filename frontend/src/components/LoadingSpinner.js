/**
 * Loading spinner indicator.
 */

/**
 * Create a loading spinner.
 * @param {string} message - Optional message below spinner
 * @returns {string} HTML
 */
export function createLoadingSpinner(message = 'Cargando...') {
  return `
    <div class="flex flex-col items-center justify-center py-16">
      <div class="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent mb-3"></div>
      <p class="text-sm text-gray-400">${message}</p>
    </div>
  `
}
