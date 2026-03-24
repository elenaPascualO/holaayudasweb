import { describe, it, expect } from 'vitest'
import { applySemanticFilters } from '../src/pages/search.js'

describe('applySemanticFilters', () => {
  const makeResults = (items) => ({
    content: items,
    totalElements: items.length,
    totalPages: 1,
    number: 0,
    size: 20,
  })

  it('sorts non-closed grants before closed ones', () => {
    const raw = makeResults([
      { fechaRecepcion: '2024-06-01', _status: 'closed', _score: 0.9 },
      { fechaRecepcion: '2024-07-01', _status: 'open', _score: 0.8 },
      { fechaRecepcion: '2024-05-01', _status: 'open', _score: 0.7 },
    ])

    const result = applySemanticFilters(raw, {}, 0, 20)

    // Non-closed first (by date desc), then closed
    expect(result.content[0]._status).toBe('open')
    expect(result.content[0].fechaRecepcion).toBe('2024-07-01')
    expect(result.content[1]._status).toBe('open')
    expect(result.content[1].fechaRecepcion).toBe('2024-05-01')
    expect(result.content[2]._status).toBe('closed')
  })

  it('sorts chronologically descending within each status group', () => {
    const raw = makeResults([
      { fechaRecepcion: '2024-01-01', _status: 'closed' },
      { fechaRecepcion: '2024-06-01', _status: 'closed' },
      { fechaRecepcion: '2024-03-01', _status: 'open' },
      { fechaRecepcion: '2024-09-01', _status: 'open' },
    ])

    const result = applySemanticFilters(raw, {}, 0, 20)

    // Open group: Sep, Mar
    expect(result.content[0].fechaRecepcion).toBe('2024-09-01')
    expect(result.content[1].fechaRecepcion).toBe('2024-03-01')
    // Closed group: Jun, Jan
    expect(result.content[2].fechaRecepcion).toBe('2024-06-01')
    expect(result.content[3].fechaRecepcion).toBe('2024-01-01')
  })

  it('treats permanent and unknown status as non-closed', () => {
    const raw = makeResults([
      { fechaRecepcion: '2024-01-01', _status: 'closed' },
      { fechaRecepcion: '2024-02-01', _status: 'permanent' },
      { fechaRecepcion: '2024-03-01', _status: 'unknown' },
    ])

    const result = applySemanticFilters(raw, {}, 0, 20)

    // permanent and unknown come before closed
    expect(result.content[0]._status).toBe('unknown')
    expect(result.content[1]._status).toBe('permanent')
    expect(result.content[2]._status).toBe('closed')
  })

  it('still applies status and year filters before sorting', () => {
    const raw = makeResults([
      { fechaRecepcion: '2024-06-01', _status: 'closed' },
      { fechaRecepcion: '2024-07-01', _status: 'open' },
      { fechaRecepcion: '2023-01-01', _status: 'open' },
    ])

    const result = applySemanticFilters(raw, { yearFrom: '2024' }, 0, 20)

    expect(result.content.length).toBe(2)
    expect(result.content[0]._status).toBe('open')
    expect(result.content[1]._status).toBe('closed')
  })
})
