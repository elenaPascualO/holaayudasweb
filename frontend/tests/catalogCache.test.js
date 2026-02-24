import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getCatalogs, resetCatalogCache } from '../src/utils/catalogCache.js'

// Mock the api module
vi.mock('../src/utils/api.js', () => ({
  getCatalog: vi.fn(),
}))

import { getCatalog } from '../src/utils/api.js'

describe('catalogCache', () => {
  beforeEach(() => {
    resetCatalogCache()
    vi.clearAllMocks()
  })

  it('fetches all three catalogs in parallel', async () => {
    getCatalog.mockImplementation((name) => {
      if (name === 'instrumentos') return Promise.resolve([{ id: 1, descripcion: 'Subvencion' }])
      if (name === 'beneficiarios') return Promise.resolve([{ id: 2, descripcion: 'Empresas' }])
      if (name === 'finalidades') return Promise.resolve([{ id: 3, descripcion: 'Cultura' }])
      return Promise.resolve([])
    })

    const result = await getCatalogs()

    expect(getCatalog).toHaveBeenCalledTimes(3)
    expect(getCatalog).toHaveBeenCalledWith('instrumentos')
    expect(getCatalog).toHaveBeenCalledWith('beneficiarios')
    expect(getCatalog).toHaveBeenCalledWith('finalidades')
    expect(result.instrumentos).toEqual([{ id: 1, descripcion: 'Subvencion' }])
    expect(result.beneficiarios).toEqual([{ id: 2, descripcion: 'Empresas' }])
    expect(result.finalidades).toEqual([{ id: 3, descripcion: 'Cultura' }])
  })

  it('caches result across calls', async () => {
    getCatalog.mockResolvedValue([{ id: 1, descripcion: 'Test' }])

    await getCatalogs()
    await getCatalogs()

    // Should only fetch once despite two calls
    expect(getCatalog).toHaveBeenCalledTimes(3)
  })

  it('returns empty arrays on error', async () => {
    getCatalog.mockRejectedValue(new Error('Network error'))

    const result = await getCatalogs()

    expect(result).toEqual({ instrumentos: [], beneficiarios: [], finalidades: [] })
  })

  it('filters items without id or descripcion', async () => {
    getCatalog.mockImplementation((name) => {
      if (name === 'instrumentos') {
        return Promise.resolve([
          { id: 1, descripcion: 'Valid' },
          { id: null, descripcion: 'No ID' },
          { id: 2, descripcion: '' },
          { id: 3, descripcion: 'Also valid' },
        ])
      }
      return Promise.resolve([])
    })

    const result = await getCatalogs()

    expect(result.instrumentos).toEqual([
      { id: 1, descripcion: 'Valid' },
      { id: 3, descripcion: 'Also valid' },
    ])
  })
})
