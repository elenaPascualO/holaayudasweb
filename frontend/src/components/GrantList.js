/**
 * List of grant cards.
 */

import { createGrantCard } from './GrantCard.js'

/**
 * Create a list of grant cards.
 * @param {Array} grants - Array of grant objects
 * @returns {string} HTML
 */
export function createGrantList(grants) {
  if (!grants || grants.length === 0) return ''

  return `
    <div class="grid gap-3">
      ${grants.map((g) => createGrantCard(g)).join('')}
    </div>
  `
}
