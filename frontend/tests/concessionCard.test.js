import { describe, it, expect } from 'vitest'
import { createConcessionCard, createConcessionList } from '../src/components/ConcessionCard.js'

describe('createConcessionCard', () => {
  it('renders beneficiary name, amount, and date', () => {
    const html = createConcessionCard({
      beneficiario: 'A12345678 - EMPRESA TEST S.L.',
      importeConcedido: 50000,
      fechaConcesion: '15/01/2026',
      descripcionInstrumento: 'Subvencion',
    })
    expect(html).toContain('EMPRESA TEST S.L.')
    expect(html).not.toContain('A12345678')
    expect(html).toContain('50.000')
    expect(html).toContain('15/01/2026')
    expect(html).toContain('Subvencion')
  })

  it('handles missing beneficiary gracefully', () => {
    const html = createConcessionCard({
      importeConcedido: 1000,
    })
    expect(html).toContain('Beneficiario no disponible')
  })

  it('parses name without NIF prefix', () => {
    const html = createConcessionCard({
      beneficiario: 'Juan Garcia Lopez',
      importeConcedido: 2000,
    })
    expect(html).toContain('Juan Garcia Lopez')
  })

  it('parses NIF with dash separator', () => {
    const html = createConcessionCard({
      beneficiario: '12345678A - PERSONA FISICA',
    })
    expect(html).toContain('PERSONA FISICA')
    expect(html).not.toContain('12345678A')
  })
})

describe('createConcessionList', () => {
  it('renders multiple cards', () => {
    const html = createConcessionList([
      { beneficiario: 'Empresa A', importeConcedido: 1000 },
      { beneficiario: 'Empresa B', importeConcedido: 2000 },
    ])
    expect(html).toContain('Empresa A')
    expect(html).toContain('Empresa B')
  })

  it('returns empty string for empty array', () => {
    expect(createConcessionList([])).toBe('')
  })

  it('returns empty string for null', () => {
    expect(createConcessionList(null)).toBe('')
  })
})
