import { describe, it, expect } from 'vitest'
import { getCachedDetail, setCachedDetail } from '../src/utils/detailCache.js'

describe('detailCache', () => {
  it('returns undefined for uncached code', () => {
    expect(getCachedDetail('999999')).toBeUndefined()
  })

  it('returns cached data after set', () => {
    const data = { descripcion: 'Test grant', presupuestoTotal: 50000 }
    setCachedDetail('123456', data)
    expect(getCachedDetail('123456')).toBe(data)
  })

  it('overwrites existing entry', () => {
    const first = { descripcion: 'First' }
    const second = { descripcion: 'Second' }
    setCachedDetail('111111', first)
    setCachedDetail('111111', second)
    expect(getCachedDetail('111111')).toBe(second)
  })

  it('stores multiple codes independently', () => {
    const a = { descripcion: 'A' }
    const b = { descripcion: 'B' }
    setCachedDetail('aaa', a)
    setCachedDetail('bbb', b)
    expect(getCachedDetail('aaa')).toBe(a)
    expect(getCachedDetail('bbb')).toBe(b)
  })
})
