/**
 * Formatting utilities for display values.
 */

const MONTH_NAMES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

/**
 * Escape HTML to prevent XSS from BDNS data.
 * @param {string} text - Raw text from API
 * @returns {string} Escaped HTML-safe string
 */
export function escapeHtml(text) {
  if (!text) return ''
  const str = String(text)
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

/**
 * Format a budget amount as Spanish currency.
 * @param {number} amount
 * @returns {string} e.g., "1.500.000,00 €"
 */
export function formatCurrency(amount) {
  if (amount == null || isNaN(amount)) return ''
  return new Intl.NumberFormat('es-ES', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

/**
 * Parse a date string from either BDNS format (dd/mm/yyyy) or ISO (YYYY-MM-DD).
 * @param {string} dateStr
 * @returns {Date|null}
 */
export function parseDate(dateStr) {
  if (!dateStr) return null

  // BDNS format: dd/mm/yyyy
  if (dateStr.includes('/')) {
    const [day, month, year] = dateStr.split('/')
    return new Date(Number(year), Number(month) - 1, Number(day))
  }

  // ISO format: YYYY-MM-DD
  if (dateStr.includes('-')) {
    const [year, month, day] = dateStr.split('-')
    return new Date(Number(year), Number(month) - 1, Number(day))
  }

  return null
}

/**
 * Format a date string to readable Spanish format.
 * @param {string} dateStr - dd/mm/yyyy or YYYY-MM-DD
 * @returns {string} e.g., "15 de enero de 2026"
 */
export function formatDate(dateStr) {
  const date = parseDate(dateStr)
  if (!date || isNaN(date.getTime())) return dateStr || ''
  return `${date.getDate()} de ${MONTH_NAMES[date.getMonth()]} de ${date.getFullYear()}`
}

/**
 * Format a date string to short format.
 * @param {string} dateStr
 * @returns {string} e.g., "15/01/2026"
 */
export function formatDateShort(dateStr) {
  const date = parseDate(dateStr)
  if (!date || isNaN(date.getTime())) return dateStr || ''
  const d = String(date.getDate()).padStart(2, '0')
  const m = String(date.getMonth() + 1).padStart(2, '0')
  return `${d}/${m}/${date.getFullYear()}`
}

/**
 * Truncate text with ellipsis.
 * @param {string} text
 * @param {number} maxLength
 * @returns {string}
 */
export function truncate(text, maxLength = 150) {
  if (!text || text.length <= maxLength) return text || ''
  return text.slice(0, maxLength).trimEnd() + '...'
}

/**
 * Format a budget amount as compact Spanish currency (e.g., "1.173M €", "45.200M €").
 * Uses abbreviations for millions and billions.
 * @param {number} amount
 * @returns {string}
 */
export function formatCurrencyCompact(amount) {
  if (amount == null || isNaN(amount)) return ''
  const abs = Math.abs(amount)
  if (abs >= 1e9) {
    const value = amount / 1e9
    return new Intl.NumberFormat('es-ES', { maximumFractionDigits: 0 }).format(value) + 'MM €'
  }
  if (abs >= 1e6) {
    const value = amount / 1e6
    return new Intl.NumberFormat('es-ES', { maximumFractionDigits: 0 }).format(value) + 'M €'
  }
  return formatCurrency(amount)
}

/**
 * Format a large number with Spanish locale separator.
 * @param {number} num
 * @returns {string} e.g., "610.576"
 */
export function formatNumber(num) {
  if (num == null || isNaN(num)) return ''
  return new Intl.NumberFormat('es-ES').format(num)
}
