import { describe, it, expect } from 'vitest'
import { parseTopBeneficiaryName, createBeneficiaryRow, createBeneficiaryList } from '../src/components/BeneficiaryRow.js'

describe('parseTopBeneficiaryName', () => {
  it('parses "ES NIF NAME" format', () => {
    const result = parseTopBeneficiaryName('ES A07129430 AIR EUROPA LINEAS AEREAS, SA')
    expect(result.nifCif).toBe('A07129430')
    expect(result.name).toBe('AIR EUROPA LINEAS AEREAS, SA')
  })

  it('parses NIF without ES prefix', () => {
    const result = parseTopBeneficiaryName('B12345678 EMPRESA SL')
    expect(result.nifCif).toBe('B12345678')
    expect(result.name).toBe('EMPRESA SL')
  })

  it('handles null/empty input', () => {
    expect(parseTopBeneficiaryName(null).name).toBe('Beneficiario no disponible')
    expect(parseTopBeneficiaryName('').name).toBe('Beneficiario no disponible')
    expect(parseTopBeneficiaryName(undefined).name).toBe('Beneficiario no disponible')
  })

  it('returns raw string when no NIF pattern found', () => {
    const result = parseTopBeneficiaryName('UNKNOWN ENTITY')
    expect(result.nifCif).toBe('')
    expect(result.name).toBe('UNKNOWN ENTITY')
  })

  it('handles personal NIF format (8 digits + letter)', () => {
    const result = parseTopBeneficiaryName('ES 12345678A JUAN GARCIA')
    expect(result.nifCif).toBe('12345678A')
    expect(result.name).toBe('JUAN GARCIA')
  })
})

describe('createBeneficiaryRow', () => {
  const item = {
    beneficiario: 'ES A07129430 AIR EUROPA LINEAS AEREAS, SA',
    ayudaETotal: 500000000,
  }

  it('renders rank number', () => {
    const html = createBeneficiaryRow(item, 1, 500000000)
    expect(html).toContain('>1</span>')
  })

  it('renders beneficiary name', () => {
    const html = createBeneficiaryRow(item, 1, 500000000)
    expect(html).toContain('AIR EUROPA LINEAS AEREAS, SA')
  })

  it('renders NIF/CIF', () => {
    const html = createBeneficiaryRow(item, 1, 500000000)
    expect(html).toContain('A07129430')
  })

  it('renders amount', () => {
    const html = createBeneficiaryRow(item, 1, 500000000)
    // Should contain formatted currency
    expect(html).toContain('€')
  })

  it('renders proportional bar', () => {
    const html = createBeneficiaryRow(item, 1, 500000000)
    expect(html).toContain('width: 100.0%')
  })

  it('renders bar with min 2% for zero amounts', () => {
    const html = createBeneficiaryRow({ ...item, ayudaETotal: 0 }, 1, 500000000)
    expect(html).toContain('width: 2.0%')
  })

  it('renders data-nif-cif attribute', () => {
    const html = createBeneficiaryRow(item, 1, 500000000)
    expect(html).toContain('data-nif-cif="A07129430"')
  })

  it('escapes HTML in names', () => {
    const malicious = { ...item, beneficiario: 'ES A07129430 <script>alert("xss")</script>' }
    const html = createBeneficiaryRow(malicious, 1, 500000000)
    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;')
  })
})

describe('createBeneficiaryList', () => {
  it('returns empty string for empty array', () => {
    expect(createBeneficiaryList([])).toBe('')
    expect(createBeneficiaryList(null)).toBe('')
  })

  it('renders multiple rows with correct ranks', () => {
    const items = [
      { beneficiario: 'ES A111 EMPRESA A', ayudaETotal: 1000 },
      { beneficiario: 'ES B222 EMPRESA B', ayudaETotal: 500 },
    ]
    const html = createBeneficiaryList(items, 1)
    expect(html).toContain('>1</span>')
    expect(html).toContain('>2</span>')
  })

  it('respects startRank offset', () => {
    const items = [
      { beneficiario: 'ES A111 EMPRESA A', ayudaETotal: 1000 },
    ]
    const html = createBeneficiaryList(items, 21)
    expect(html).toContain('>21</span>')
  })
})
