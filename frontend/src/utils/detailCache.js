/**
 * In-memory cache for grant detail data.
 * Persists for the browser session lifetime (no TTL).
 */

const cache = new Map()

/**
 * Get cached detail for a grant code.
 * @param {string} code - BDNS code
 * @returns {Object|undefined}
 */
export function getCachedDetail(code) {
  return cache.get(code)
}

/**
 * Store grant detail in cache.
 * @param {string} code - BDNS code
 * @param {Object} data - Grant detail data
 */
export function setCachedDetail(code, data) {
  cache.set(code, data)
}
