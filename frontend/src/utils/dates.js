/**
 * Date calculation helpers for grant status.
 */

import { parseDate } from './formatters.js'

/**
 * Determine the application status of a grant.
 * @param {Object} grant - Grant detail object from BDNS
 * @returns {'open'|'closed'|'upcoming'|'permanent'|'unknown'}
 */
export function getGrantStatus(grant) {
  if (!grant) return 'unknown'

  const now = new Date()
  now.setHours(0, 0, 0, 0)

  // If marked as permanently open with no end date
  if (grant.abierto === true && !grant.fechaFinSolicitud) {
    return 'permanent'
  }

  const startDate = parseDate(grant.fechaInicioSolicitud || grant.textInicio)
  const endDate = parseDate(grant.fechaFinSolicitud || grant.textFin)

  // Has an end date in the past → closed
  if (endDate && endDate < now) {
    return 'closed'
  }

  // Has a start date in the future → upcoming
  if (startDate && startDate > now) {
    return 'upcoming'
  }

  // Has an end date in the future (and start date is past or absent) → open
  if (endDate && endDate >= now) {
    return 'open'
  }

  // abierto flag from BDNS
  if (grant.abierto === true) {
    return 'open'
  }

  return 'unknown'
}

/**
 * Calculate days remaining until deadline.
 * @param {string} dateStr - End date string
 * @returns {number|null} Days remaining, null if no deadline or past
 */
export function daysUntilDeadline(dateStr) {
  const endDate = parseDate(dateStr)
  if (!endDate) return null

  const now = new Date()
  now.setHours(0, 0, 0, 0)
  endDate.setHours(0, 0, 0, 0)

  const diffMs = endDate.getTime() - now.getTime()
  if (diffMs < 0) return null

  return Math.ceil(diffMs / (1000 * 60 * 60 * 24))
}

/**
 * Get urgency level based on days remaining.
 * @param {number|null} days
 * @returns {'urgent'|'warning'|'normal'|null}
 */
export function getUrgencyLevel(days) {
  if (days == null) return null
  if (days <= 7) return 'urgent'
  if (days <= 30) return 'warning'
  return 'normal'
}
