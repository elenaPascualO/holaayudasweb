/**
 * Row component for top beneficiaries ranking with visual bars and drill-down.
 */

import { escapeHtml, formatCurrency } from '../utils/formatters.js'

/**
 * Parse a top beneficiary name from BDNS format.
 * Input format: "ES A07129430 AIR EUROPA LINEAS AEREAS, SA"
 * Also handles: "A07129430 EMPRESA SL" (without ES prefix)
 * @param {string} raw - Raw beneficiary string
 * @returns {{ nifCif: string, name: string }}
 */
export function parseTopBeneficiaryName(raw) {
  if (!raw || typeof raw !== 'string') {
    return { nifCif: '', name: 'Beneficiario no disponible' }
  }

  const trimmed = raw.trim()

  // Pattern: optional "ES " prefix + NIF/CIF (letter? + 7-8 digits + letter?) + space + name
  const match = trimmed.match(/^(?:ES\s+)?([A-Z]?\d{7,8}[A-Z]?)\s+(.+)$/i)
  if (match) {
    return { nifCif: match[1].toUpperCase(), name: match[2].trim() }
  }

  return { nifCif: '', name: trimmed }
}

/**
 * Create a single beneficiary row with visual bar.
 * @param {Object} item - Top beneficiary data from BDNS
 * @param {number} rank - Position in ranking (1-indexed)
 * @param {number} maxAmount - Largest amount on this page (for bar scaling)
 * @returns {string} HTML
 */
export function createBeneficiaryRow(item, rank, maxAmount) {
  const { nifCif, name } = parseTopBeneficiaryName(item.beneficiario || '')
  const amount = item.ayudaETotal || 0
  const barPercent = maxAmount > 0 ? Math.max(2, (amount / maxAmount) * 100) : 2

  return `
    <div class="beneficiary-row border-b border-gray-50 last:border-0" data-nif-cif="${escapeHtml(nifCif)}">
      <div class="flex items-center gap-3 py-3 cursor-pointer hover:bg-gray-50/50 px-2 -mx-2 rounded-lg transition-colors"
           data-expand-beneficiary="${escapeHtml(nifCif)}">
        <span class="text-sm font-mono text-gray-300 w-8 text-right shrink-0">${rank}</span>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <p class="text-sm font-medium text-gray-900 truncate">${escapeHtml(name)}</p>
            ${nifCif ? `<span class="text-xs font-mono text-gray-400 shrink-0">${escapeHtml(nifCif)}</span>` : ''}
          </div>
          <div class="w-full bg-gray-100 rounded-full h-2">
            <div class="bg-primary/70 h-2 rounded-full transition-all" style="width: ${barPercent.toFixed(1)}%"></div>
          </div>
        </div>
        <span class="text-sm font-semibold text-gray-900 whitespace-nowrap shrink-0">
          ${formatCurrency(amount)}
        </span>
        <svg class="w-4 h-4 text-gray-400 shrink-0 transition-transform expand-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
        </svg>
      </div>
      <div class="concesiones-container hidden pl-11 pb-3"></div>
    </div>
  `
}

/**
 * Create a list of beneficiary rows.
 * @param {Array} items - Array of top beneficiary objects
 * @param {number} [startRank=1] - Starting rank number
 * @param {number} [globalMax] - Global max amount (from page 0 #1) for consistent bars across pages
 * @returns {string} HTML
 */
export function createBeneficiaryList(items, startRank = 1, globalMax) {
  if (!items || items.length === 0) return ''
  const maxAmount = globalMax || Math.max(...items.map((i) => i.ayudaETotal || 0))
  return `
    <div class="divide-y divide-gray-50">
      ${items.map((item, i) => createBeneficiaryRow(item, startRank + i, maxAmount)).join('')}
    </div>
  `
}
