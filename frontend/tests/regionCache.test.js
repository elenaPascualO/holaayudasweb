import { describe, it, expect } from 'vitest'
import { COMMUNITIES, PROVINCES } from '../src/utils/regionCache.js'

describe('COMMUNITIES', () => {
  it('contains 19 autonomous communities (including Ceuta and Melilla)', () => {
    expect(COMMUNITIES).toHaveLength(19)
  })

  it('is sorted alphabetically', () => {
    const names = COMMUNITIES.map((c) => c.name)
    const sorted = [...names].sort((a, b) => a.localeCompare(b, 'es'))
    expect(names).toEqual(sorted)
  })

  it('each entry has id and name', () => {
    for (const c of COMMUNITIES) {
      expect(c).toHaveProperty('id')
      expect(c).toHaveProperty('name')
      expect(typeof c.id).toBe('number')
      expect(typeof c.name).toBe('string')
      expect(c.name.length).toBeGreaterThan(0)
    }
  })

  it('includes known communities', () => {
    const names = COMMUNITIES.map((c) => c.name)
    expect(names).toContain('Andalucia')
    expect(names).toContain('Cataluña')
    expect(names).toContain('Galicia')
    expect(names).toContain('Comunidad de Madrid')
  })
})

describe('PROVINCES', () => {
  it('contains all Spanish provinces', () => {
    expect(PROVINCES.length).toBeGreaterThanOrEqual(50)
  })

  it('is sorted alphabetically', () => {
    const names = PROVINCES.map((p) => p.name)
    const sorted = [...names].sort((a, b) => a.localeCompare(b, 'es'))
    expect(names).toEqual(sorted)
  })

  it('each entry has id and name', () => {
    for (const p of PROVINCES) {
      expect(p).toHaveProperty('id')
      expect(p).toHaveProperty('name')
      expect(typeof p.id).toBe('number')
      expect(typeof p.name).toBe('string')
      expect(p.name.length).toBeGreaterThan(0)
    }
  })

  it('includes known provinces', () => {
    const names = PROVINCES.map((p) => p.name)
    expect(names).toContain('Barcelona')
    expect(names).toContain('Madrid')
    expect(names).toContain('Sevilla')
    expect(names).toContain('A Coruña')
  })
})
