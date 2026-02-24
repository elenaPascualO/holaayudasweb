/**
 * Fetch and cache BDNS catalogs (instrumentos, beneficiarios, finalidades).
 * Single fetch per session — subsequent calls return the cached value.
 */

import { getCatalog } from './api.js'

/** @type {Promise<{instrumentos: Array, beneficiarios: Array, finalidades: Array}> | null} */
let catalogPromise = null

/**
 * Get all filter catalogs (fetches once, caches for the session).
 * @returns {Promise<{instrumentos: Array<{id: number, descripcion: string}>, beneficiarios: Array<{id: number, descripcion: string}>, finalidades: Array<{id: number, descripcion: string}>}>}
 */
export function getCatalogs() {
  if (!catalogPromise) {
    catalogPromise = fetchAllCatalogs()
  }
  return catalogPromise
}

async function fetchAllCatalogs() {
  try {
    const [instrumentos, beneficiarios, finalidades] = await Promise.all([
      getCatalog('instrumentos'),
      getCatalog('beneficiarios'),
      getCatalog('finalidades'),
    ])
    return {
      instrumentos: normalizeCatalog(instrumentos),
      beneficiarios: normalizeCatalog(beneficiarios),
      finalidades: normalizeCatalog(finalidades),
    }
  } catch {
    // Return empty arrays on error so the UI still renders
    return { instrumentos: [], beneficiarios: [], finalidades: [] }
  }
}

/**
 * Normalize catalog data into a flat array of {id, descripcion}.
 * BDNS catalogs may return different shapes depending on the endpoint.
 * @param {any} data - Raw catalog response
 * @returns {Array<{id: number, descripcion: string}>}
 */
function normalizeCatalog(data) {
  if (!data) return []
  // Already an array of objects with id + descripcion
  if (Array.isArray(data)) {
    return data
      .filter((item) => item && item.id != null && item.descripcion)
      .map((item) => ({ id: item.id, descripcion: item.descripcion }))
  }
  return []
}

/**
 * Reset the cache (useful for testing).
 */
export function resetCatalogCache() {
  catalogPromise = null
}
