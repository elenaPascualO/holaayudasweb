/**
 * Umami analytics event tracking wrapper.
 * Checks availability before tracking and skips localhost.
 */

/**
 * Check if tracking should be skipped (localhost or manually disabled).
 * Disable in your browser: localStorage.setItem('umami.disabled', '1')
 * @returns {boolean}
 */
function isTrackingDisabled() {
  if (typeof window === 'undefined') return true
  const hostname = window.location.hostname
  if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0') return true
  try {
    return localStorage.getItem('umami.disabled') === '1'
  } catch {
    return false
  }
}

/**
 * Track an event in Umami.
 * @param {string} event - Event name
 * @param {Object} [data] - Additional event data
 */
export function track(event, data = {}) {
  if (typeof window !== 'undefined' && window.umami && !isTrackingDisabled()) {
    window.umami.track(event, data)
  }
}

// Predefined event names for consistency
export const events = {
  // Search
  SEARCH_SUBMIT: 'search-submit',
  QUICK_FILTER: 'quick-filter',

  // Filters
  FILTER_APPLY: 'filter-apply',
  FILTER_CLEAR: 'filter-clear',
  SORT_CHANGE: 'sort-change',

  // Grant detail
  DETAIL_VIEW: 'detail-view',
  DETAIL_APPLY: 'detail-apply',
  DETAIL_DOCUMENT: 'detail-document',
  DETAIL_BASES: 'detail-bases',
  DETAIL_OFFICIAL: 'detail-official',
  CONCESIONES_VIEW: 'concesiones-view',

  // Transparencia
  BENEFICIARIOS_VIEW: 'beneficiarios-view',
  BENEFICIARIOS_FILTER: 'beneficiarios-filter',
  BENEFICIARIOS_DRILL_DOWN: 'beneficiarios-drill-down',

  // Feedback
  FEEDBACK_OPEN: 'feedback-open',
  FEEDBACK_SUBMIT: 'feedback-submit',

  // Pagination
  PAGINATION: 'pagination',
}
