/**
 * Umami analytics event tracking wrapper.
 * Checks availability before tracking and skips localhost.
 */

/**
 * Check if running on localhost (skip tracking in dev).
 * @returns {boolean}
 */
function isLocalhost() {
  if (typeof window === 'undefined') return false
  const hostname = window.location.hostname
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0'
}

/**
 * Track an event in Umami.
 * @param {string} event - Event name
 * @param {Object} [data] - Additional event data
 */
export function track(event, data = {}) {
  if (typeof window !== 'undefined' && window.umami && !isLocalhost()) {
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

  // Feedback
  FEEDBACK_OPEN: 'feedback-open',
  FEEDBACK_SUBMIT: 'feedback-submit',

  // Pagination
  PAGINATION: 'pagination',
}
