/**
 * Grant detail page.
 */

import { getGrantDetailCached } from '../utils/api.js'
import { createGrantDetail } from '../components/GrantDetail.js'
import { escapeHtml } from '../utils/formatters.js'

/**
 * Render the grant detail page.
 * @param {string} bdnsCode - BDNS code
 * @returns {Promise<string>} HTML
 */
export async function renderDetailPage(bdnsCode) {
  try {
    const grant = await getGrantDetailCached(bdnsCode)
    return createGrantDetail(grant)
  } catch {
    return `
      <div class="text-center py-16 max-w-md mx-auto">
        <div class="text-5xl mb-4">😕</div>
        <h2 class="text-xl font-semibold text-gray-700 mb-2">
          No se pudo cargar la ayuda
        </h2>
        <p class="text-gray-400 mb-1">
          Codigo BDNS: <span class="font-mono">${escapeHtml(bdnsCode)}</span>
        </p>
        <p class="text-sm text-gray-400 mb-6">
          Es posible que la convocatoria no exista o que haya un error de conexion.
        </p>
        <a href="/" data-link
           class="inline-flex items-center gap-1 text-primary hover:underline text-sm font-medium no-underline">
          ← Volver al inicio
        </a>
      </div>
    `
  }
}
