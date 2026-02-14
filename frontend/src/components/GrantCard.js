/**
 * Grant result card for search results and latest feed.
 */

import { escapeHtml, formatDate, formatCurrency } from '../utils/formatters.js'
import { getGrantStatus } from '../utils/dates.js'
import { createStatusBadge } from './StatusBadge.js'

/**
 * Create a grant card.
 * @param {Object} grant - Grant data from BDNS search
 * @returns {string} HTML
 */
export function createGrantCard(grant) {
  const status = grant._status || getGrantStatus(grant)
  const convocante = [grant.nivel2, grant.nivel1].filter(Boolean).join(' · ')
  const code = escapeHtml(grant.numeroConvocatoria)

  const enriched = !!grant._status
  const budgetHtml = grant._presupuestoTotal
    ? `<span data-grant-budget="${code}"
             class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700"
       >${formatCurrency(grant._presupuestoTotal)}</span>`
    : `<span data-grant-budget="${code}"></span>`

  return `
    <article
      class="bg-white rounded-xl border border-gray-100 p-5 hover:shadow-md
             hover:border-gray-200 transition-all cursor-pointer group"
      data-link="/ayuda/${code}"
      ${enriched ? 'data-enriched' : ''}
    >
      <div class="flex gap-3">
        <div class="flex-1 min-w-0">
          <h3 class="font-semibold text-gray-900 line-clamp-2 mb-1.5
                     group-hover:text-primary transition-colors">
            ${escapeHtml(grant.descripcion)}
          </h3>
          <p class="text-sm text-gray-500 mb-2 truncate">
            ${escapeHtml(convocante)}
          </p>
          <div class="flex items-center gap-3 text-xs text-gray-400">
            <span>${formatDate(grant.fechaRecepcion)}</span>
            <span class="font-mono bg-gray-50 px-1.5 py-0.5 rounded">
              BDNS ${code}
            </span>
          </div>
        </div>
        <div class="shrink-0 flex flex-col items-end justify-between">
          <div data-grant-badge="${code}">
            ${(enriched || status !== 'unknown') ? createStatusBadge(status) : ''}
          </div>
          ${budgetHtml}
        </div>
      </div>
    </article>
  `
}
