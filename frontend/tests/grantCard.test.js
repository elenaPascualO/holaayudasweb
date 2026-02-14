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
})
