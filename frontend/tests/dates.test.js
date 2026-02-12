import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { getGrantStatus, daysUntilDeadline, getUrgencyLevel } from '../src/utils/dates.js'

describe('getGrantStatus', () => {
  beforeEach(() => {
    // Mock current date to 2026-02-12
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 1, 12))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns "permanent" when open with no end date', () => {
    expect(getGrantStatus({ abierto: true })).toBe('permanent')
  })

  it('returns "open" when end date is in the future', () => {
    expect(
      getGrantStatus({ fechaFinSolicitud: '30/06/2026' })
    ).toBe('open')
  })

  it('returns "closed" when end date is in the past', () => {
    expect(
      getGrantStatus({ fechaFinSolicitud: '01/01/2026' })
    ).toBe('closed')
  })

  it('returns "upcoming" when start date is in the future', () => {
    expect(
      getGrantStatus({
        fechaInicioSolicitud: '01/03/2026',
        fechaFinSolicitud: '30/06/2026',
      })
    ).toBe('upcoming')
  })

  it('returns "unknown" for null grant', () => {
    expect(getGrantStatus(null)).toBe('unknown')
  })

  it('returns "unknown" for grant with no dates or status', () => {
    expect(getGrantStatus({})).toBe('unknown')
  })
})

describe('daysUntilDeadline', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 1, 12)) // 2026-02-12
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns days remaining for future date', () => {
    // 28 Feb = 16 days from 12 Feb
    expect(daysUntilDeadline('28/02/2026')).toBe(16)
  })

  it('returns null for past date', () => {
    expect(daysUntilDeadline('01/01/2026')).toBeNull()
  })

  it('returns null for null input', () => {
    expect(daysUntilDeadline(null)).toBeNull()
  })

  it('returns 0 for today', () => {
    expect(daysUntilDeadline('12/02/2026')).toBe(0)
  })
})

describe('getUrgencyLevel', () => {
  it('returns "urgent" for 7 or fewer days', () => {
    expect(getUrgencyLevel(7)).toBe('urgent')
    expect(getUrgencyLevel(1)).toBe('urgent')
    expect(getUrgencyLevel(0)).toBe('urgent')
  })

  it('returns "warning" for 8-30 days', () => {
    expect(getUrgencyLevel(30)).toBe('warning')
    expect(getUrgencyLevel(15)).toBe('warning')
  })

  it('returns "normal" for more than 30 days', () => {
    expect(getUrgencyLevel(31)).toBe('normal')
    expect(getUrgencyLevel(100)).toBe('normal')
  })

  it('returns null for null input', () => {
    expect(getUrgencyLevel(null)).toBeNull()
  })
})
