import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock detailCache before importing api module
vi.mock('../src/utils/detailCache.js', () => {
  const store = new Map()
  return {
    getCachedDetail: vi.fn((code) => store.get(code)),
    setCachedDetail: vi.fn((code, data) => store.set(code, data)),
    __store: store,
  }
})

// Mock global fetch
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

import { getGrantDetailCached } from '../src/utils/api.js'
import { getCachedDetail, setCachedDetail, __store } from '../src/utils/detailCache.js'

describe('getGrantDetailCached', () => {
  const mockDetail = { descripcion: 'Test', presupuestoTotal: 10000 }

  beforeEach(() => {
    vi.clearAllMocks()
    __store.clear()
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDetail),
    })
  })

  it('fetches from API on cache miss and caches result', async () => {
    const result = await getGrantDetailCached('123456')

    expect(result).toEqual(mockDetail)
    expect(mockFetch).toHaveBeenCalledOnce()
    expect(setCachedDetail).toHaveBeenCalledWith('123456', mockDetail)
  })

  it('returns cached data without fetching on cache hit', async () => {
    __store.set('789', mockDetail)

    const result = await getGrantDetailCached('789')

    expect(result).toEqual(mockDetail)
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('propagates API errors on cache miss', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
      text: () => Promise.resolve('Not found'),
    })

    await expect(getGrantDetailCached('000')).rejects.toThrow('API error 404')
    expect(setCachedDetail).not.toHaveBeenCalledWith('000', expect.anything())
  })
})
