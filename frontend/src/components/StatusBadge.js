/**
 * Visual badge showing grant application status.
 */

const STATUS_CONFIG = {
  open: { label: 'Abierta', classes: 'bg-open/10 text-open' },
  closed: { label: 'Cerrada', classes: 'bg-closed/10 text-closed' },
  upcoming: { label: 'Proxima', classes: 'bg-upcoming/10 text-upcoming' },
  permanent: { label: 'Permanente', classes: 'bg-primary/10 text-primary' },
  unknown: { label: 'Sin info', classes: 'bg-gray-100 text-gray-500' },
}

/**
 * Create a status badge.
 * @param {string} status - 'open'|'closed'|'upcoming'|'permanent'|'unknown'
 * @returns {string} HTML
 */
export function createStatusBadge(status) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.unknown
  return `
    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${config.classes}">
      ${config.label}
    </span>
  `
}
