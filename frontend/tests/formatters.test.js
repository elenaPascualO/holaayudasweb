import { describe, it, expect } from 'vitest'
import {
  escapeHtml,
  formatCurrency,
  formatDate,
  formatDateShort,
  truncate,
  formatNumber,
  parseDate,
} from '../src/utils/formatters.js'

describe('escapeHtml', () => {
  it('escapes special characters', () => {
    expect(escapeHtml('<script>alert("xss")</script>')).toBe(
      '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
    )
  })

  it('handles ampersands', () => {
    expect(escapeHtml('A & B')).toBe('A &amp; B')
  })

  it('returns empty string for null/undefined', () => {
    expect(escapeHtml(null)).toBe('')
    expect(escapeHtml(undefined)).toBe('')
  })

  it('converts non-string values', () => {
    expect(escapeHtml(123)).toBe('123')
  })
})

describe('formatCurrency', () => {
  it('formats amounts in Spanish locale', () => {
    const result = formatCurrency(1500000)
    expect(result).toContain('1.500.000')
    expect(result).toContain('€')
  })

  it('formats zero', () => {
    const result = formatCurrency(0)
    expect(result).toContain('0')
  })

  it('returns empty string for null', () => {
    expect(formatCurrency(null)).toBe('')
  })

  it('returns empty string for NaN', () => {
    expect(formatCurrency(NaN)).toBe('')
  })
})

describe('parseDate', () => {
  it('parses BDNS format dd/mm/yyyy', () => {
    const date = parseDate('15/01/2026')
    expect(date.getFullYear()).toBe(2026)
    expect(date.getMonth()).toBe(0) // January
    expect(date.getDate()).toBe(15)
  })

  it('parses ISO format YYYY-MM-DD', () => {
    const date = parseDate('2026-01-15')
    expect(date.getFullYear()).toBe(2026)
    expect(date.getMonth()).toBe(0)
    expect(date.getDate()).toBe(15)
  })

  it('returns null for null/empty input', () => {
    expect(parseDate(null)).toBeNull()
    expect(parseDate('')).toBeNull()
  })
})

describe('formatDate', () => {
  it('formats BDNS date to readable Spanish', () => {
    expect(formatDate('15/01/2026')).toBe('15 de enero de 2026')
  })

  it('formats ISO date to readable Spanish', () => {
    expect(formatDate('2026-03-20')).toBe('20 de marzo de 2026')
  })

  it('returns original string for invalid format', () => {
    expect(formatDate('invalid')).toBe('invalid')
  })

  it('returns empty string for null', () => {
    expect(formatDate(null)).toBe('')
  })
})

describe('formatDateShort', () => {
  it('formats to dd/mm/yyyy', () => {
    expect(formatDateShort('2026-01-05')).toBe('05/01/2026')
  })
})

describe('truncate', () => {
  it('does not truncate short text', () => {
    expect(truncate('Hello', 10)).toBe('Hello')
  })

  it('truncates long text with ellipsis', () => {
    const long = 'a'.repeat(200)
    const result = truncate(long, 50)
    expect(result.length).toBeLessThanOrEqual(53) // 50 + '...'
    expect(result).toContain('...')
  })

  it('returns empty string for null', () => {
    expect(truncate(null)).toBe('')
  })
})

describe('formatNumber', () => {
  it('formats with Spanish locale separators', () => {
    expect(formatNumber(610576)).toBe('610.576')
  })

  it('returns empty string for null', () => {
    expect(formatNumber(null)).toBe('')
  })
})
