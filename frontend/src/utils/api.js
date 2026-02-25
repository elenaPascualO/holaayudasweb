/**
 * API client for the Hola Ayudas backend proxy.
 * All requests go through /api/* which Vite proxies to the backend in dev.
 */

import { getCachedDetail, setCachedDetail } from './detailCache.js'

const BASE = '/api'

/**
 * Generic fetch wrapper with error handling.
 * @param {string} url - Full URL to fetch
 * @param {Object} [options] - Fetch options
 * @param {number} [options.timeout] - Timeout in milliseconds
 * @returns {Promise<any>} Parsed JSON response
 */
async function fetchJson(url, options = {}) {
  const fetchOptions = {}
  if (options.timeout) {
    const controller = new AbortController()
    fetchOptions.signal = controller.signal
    setTimeout(() => controller.abort(), options.timeout)
  }
  const response = await fetch(url, fetchOptions)
  if (!response.ok) {
    const text = await response.text().catch(() => 'Unknown error')
    throw new Error(`API error ${response.status}: ${text}`)
  }
  return response.json()
}

/**
 * Build a query string from an object, omitting null/undefined/empty values.
 * @param {Object} params
 * @returns {string}
 */
function buildQuery(params) {
  const entries = Object.entries(params).filter(
    ([, v]) => v != null && v !== '' && v !== undefined
  )
  if (entries.length === 0) return ''
  return '?' + new URLSearchParams(entries).toString()
}

/**
 * Search grants with filters.
 * @param {Object} params - Search parameters
 * @param {string} [params.q] - Search text
 * @param {number} [params.page] - Page number (0-indexed)
 * @param {number} [params.pageSize] - Results per page
 * @param {string} [params.fechaDesde] - Start date (YYYY-MM-DD)
 * @param {string} [params.fechaHasta] - End date (YYYY-MM-DD)
 * @param {string} [params.tipoAdministracion] - C, A, L, or O
 * @param {string} [params.regiones] - Region IDs (comma-separated)
 * @param {string} [params.orden] - Sort direction: asc or desc
 * @returns {Promise<Object>} Paginated results
 */
export async function searchGrants(params = {}) {
  return fetchJson(`${BASE}/convocatorias${buildQuery(params)}`)
}

/**
 * Get latest published grants.
 * @param {number} [page=0] - Page number
 * @param {number} [pageSize=10] - Results per page
 * @returns {Promise<Object>} Paginated results
 */
export async function getLatestGrants(page = 0, pageSize = 10) {
  return fetchJson(`${BASE}/convocatorias/ultimas?page=${page}&pageSize=${pageSize}`)
}

/**
 * Get full detail of a specific grant.
 * @param {string} bdnsCode - The BDNS code
 * @returns {Promise<Object>} Grant detail
 */
export async function getGrantDetail(bdnsCode) {
  return fetchJson(`${BASE}/convocatorias/${encodeURIComponent(bdnsCode)}`)
}

/**
 * Get grant detail with frontend in-memory cache.
 * @param {string} bdnsCode - The BDNS code
 * @returns {Promise<Object>} Grant detail
 */
export async function getGrantDetailCached(bdnsCode) {
  const cached = getCachedDetail(bdnsCode)
  if (cached) return cached
  const data = await getGrantDetail(bdnsCode)
  setCachedDetail(bdnsCode, data)
  return data
}

/**
 * Get concessions for a specific grant.
 * @param {string} bdnsCode - BDNS convocatoria code
 * @param {number} [page=0] - Page number
 * @param {number} [pageSize=20] - Results per page
 * @returns {Promise<Object>} Paginated concession results
 */
export async function getConcesionesByGrant(bdnsCode, page = 0, pageSize = 20) {
  return fetchJson(`${BASE}/concesiones${buildQuery({ bdnsCode, page, pageSize })}`)
}

/**
 * Quick probe to get totalElements for a grant's concessions.
 * Uses a short timeout to fail fast for massive datasets.
 * @param {string} bdnsCode - BDNS convocatoria code
 * @param {number} [timeout=8000] - Timeout in ms
 * @returns {Promise<Object>} Paginated response (1 item)
 */
export async function getConcesionesCount(bdnsCode, timeout = 8000) {
  return fetchJson(
    `${BASE}/concesiones${buildQuery({ bdnsCode, page: 0, pageSize: 1 })}`,
    { timeout }
  )
}

/**
 * Search concessions with filters.
 * @param {Object} params - Search parameters (bdnsCode, nifCif, page, pageSize)
 * @returns {Promise<Object>} Paginated concession results
 */
export async function searchConcesiones(params = {}) {
  return fetchJson(`${BASE}/concesiones${buildQuery(params)}`)
}

/**
 * Get a catalog by name.
 * @param {string} name - regiones|finalidades|instrumentos|actividades|beneficiarios
 * @returns {Promise<Array>} Catalog data
 */
export async function getCatalog(name) {
  return fetchJson(`${BASE}/catalogo/${encodeURIComponent(name)}`)
}

/**
 * Search top beneficiaries.
 * @param {Object} params - Search parameters (page, pageSize, order, direccion, anio, nifCif)
 * @returns {Promise<Object>} Paginated results
 */
export async function searchTopBeneficiaries(params = {}) {
  return fetchJson(`${BASE}/beneficiarios-top${buildQuery(params)}`)
}

/**
 * Get available years for top beneficiaries.
 * @returns {Promise<Array>} List of years
 */
export async function getTopBeneficiariesYears() {
  return fetchJson(`${BASE}/beneficiarios-top/anios`)
}

/**
 * Submit user feedback.
 * @param {Object} data - { email?: string, message: string }
 * @returns {Promise<Object>} Response
 */
export async function submitFeedback(data) {
  const response = await fetch(`${BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const text = await response.text().catch(() => 'Unknown error')
    throw new Error(`API error ${response.status}: ${text}`)
  }
  return response.json()
}
