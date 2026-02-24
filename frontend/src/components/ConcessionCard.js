/**
 * Compact card for a concession (beneficiary who received a grant).
 */

import { escapeHtml, formatCurrency, formatDateShort } from '../utils/formatters.js'

/**
 * Parse beneficiary name — remove leading NIF/CIF if present.
 * BDNS often returns "A12345678 - EMPRESA S.L." or "12345678A NOMBRE".
 * @param {string} raw - Raw beneficiary string
 * @returns {string} Clean name
 */
function parseBeneficiaryName(raw) {
  if (!raw) return 'Beneficiario no disponible'
  // Pattern: optional letter + 8 digits + optional letter, then separator
  const match = raw.match(/^[A-Z]?\d{7,8}[A-Z]?\s*[-–—·]\s*(.+)$/i)
  if (match) return match[1].trim()
  return raw.trim()
}

/**
 * Create a concession card.
 * @param {Object} concession - Concession data from BDNS
 * @param {Object} [options] - Display options
 * @param {boolean} [options.showConvocatoria] - Show convocatoria name with link to detail
 * @returns {string} HTML
 */
export function createConcessionCard(concession, options = {}) {
  const name = parseBeneficiaryName(
    concession.beneficiario || concession.denominacion || ''
  )
  const amount = concession.importeConcedido || concession.importe
  const date = concession.fechaConcesion || concession.fechaResolucion || ''
  const instrument = concession.descripcionInstrumento || ''
  const convCode = concession.numeroConvocatoria || ''
  const convTitle = concession.convocatoria || ''

  return `
    <div class="flex items-center justify-between gap-3 py-3 border-b border-gray-50 last:border-0">
      <div class="min-w-0 flex-1">
        <p class="text-sm font-medium text-gray-900 truncate">
          ${escapeHtml(name)}
        </p>
        ${options.showConvocatoria && convCode ? `
          <a href="/ayuda/${encodeURIComponent(convCode)}" data-link
             class="block text-xs text-primary hover:underline truncate mt-0.5 no-underline">
            ${escapeHtml(convTitle || `Convocatoria ${convCode}`)}
          </a>
        ` : ''}
        <div class="flex items-center gap-2 mt-0.5">
          ${date ? `
            <span class="text-xs text-gray-400">${formatDateShort(date)}</span>
          ` : ''}
          ${instrument ? `
            <span class="text-xs text-gray-400">${escapeHtml(instrument)}</span>
          ` : ''}
        </div>
      </div>
      ${amount != null ? `
        <span class="text-sm font-semibold text-gray-900 whitespace-nowrap">
          ${formatCurrency(amount)}
        </span>
      ` : ''}
    </div>
  `
}

/**
 * Create a list of concession cards.
 * @param {Array} concessions - Array of concession objects
 * @param {Object} [options] - Display options passed to each card
 * @returns {string} HTML
 */
export function createConcessionList(concessions, options = {}) {
  if (!concessions || concessions.length === 0) return ''
  return `
    <div class="divide-y divide-gray-50">
      ${concessions.map((c) => createConcessionCard(c, options)).join('')}
    </div>
  `
}
