import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createGrantCard } from '../src/components/GrantCard.js'

describe('createGrantCard', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 1, 12))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  const baseGrant = {
    numeroConvocatoria: '812345',
    descripcion: 'Ayuda para innovacion',
    nivel1: 'Ministerio de Ciencia',
    nivel2: 'Gobierno de España',
    fechaRecepcion: '10/02/2026',
  }

  it('renders data-grant-badge attribute with grant code', () => {
    const html = createGrantCard(baseGrant)
    expect(html).toContain('data-grant-badge="812345"')
  })

  it('renders data-grant-budget attribute with grant code', () => {
    const html = createGrantCard(baseGrant)
    expect(html).toContain('data-grant-budget="812345"')
  })

  it('renders empty badge container when status is unknown', () => {
    const html = createGrantCard(baseGrant)
    const parser = new DOMParser()
    const doc = parser.parseFromString(html, 'text/html')
    const badgeEl = doc.querySelector('[data-grant-badge="812345"]')
    expect(badgeEl).not.toBeNull()
    // No badge content when status is unknown
    expect(badgeEl.querySelector('span')).toBeNull()
  })

  it('renders badge when status is known', () => {
    const grant = { ...baseGrant, fechaFinSolicitud: '30/06/2026' }
    const html = createGrantCard(grant)
    const parser = new DOMParser()
    const doc = parser.parseFromString(html, 'text/html')
    const badgeEl = doc.querySelector('[data-grant-badge="812345"]')
    expect(badgeEl).not.toBeNull()
    expect(badgeEl.textContent.trim()).toBe('Abierta')
  })

  it('renders budget placeholder in right column with badge', () => {
    const html = createGrantCard(baseGrant)
    const parser = new DOMParser()
    const doc = parser.parseFromString(html, 'text/html')
    const budgetEl = doc.querySelector('[data-grant-budget="812345"]')
    expect(budgetEl).not.toBeNull()
    expect(budgetEl.textContent).toBe('')
    // Budget and badge share the same right column parent
    const badgeEl = doc.querySelector('[data-grant-badge="812345"]')
    expect(budgetEl.parentElement).toBe(badgeEl.parentElement)
  })

  it('escapes HTML in grant description', () => {
    const grant = { ...baseGrant, descripcion: '<script>alert("xss")</script>' }
    const html = createGrantCard(grant)
    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;')
  })

  it('renders data-link with grant code', () => {
    const html = createGrantCard(baseGrant)
    expect(html).toContain('data-link="/ayuda/812345"')
  })

  it('renders region label when _regionLabel is present', () => {
    const grant = { ...baseGrant, _regionLabel: 'COMUNIDAD DE MADRID' }
    const html = createGrantCard(grant)
    expect(html).toContain('COMUNIDAD DE MADRID')
    // Should be in a span with same styling as BDNS code
    const parser = new DOMParser()
    const doc = parser.parseFromString(html, 'text/html')
    const spans = doc.querySelectorAll('.font-mono.bg-gray-50')
    const regionSpan = Array.from(spans).find(s => s.textContent.includes('COMUNIDAD DE MADRID'))
    expect(regionSpan).not.toBeNull()
  })

  it('does not render region label when _regionLabel is absent', () => {
    const html = createGrantCard(baseGrant)
    const parser = new DOMParser()
    const doc = parser.parseFromString(html, 'text/html')
    const spans = doc.querySelectorAll('.font-mono.bg-gray-50')
    // Only the BDNS code span
    expect(spans.length).toBe(1)
    expect(spans[0].textContent).toContain('BDNS')
  })

  it('escapes HTML in region label', () => {
    const grant = { ...baseGrant, _regionLabel: '<img src=x onerror=alert(1)>' }
    const html = createGrantCard(grant)
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;img')
  })
})
