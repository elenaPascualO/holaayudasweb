/**
 * Full grant detail view.
 */

import { escapeHtml, formatCurrency, formatDate, formatDateShort } from '../utils/formatters.js'
import { getGrantStatus, daysUntilDeadline, getUrgencyLevel } from '../utils/dates.js'
import { createStatusBadge } from './StatusBadge.js'

/**
 * Create the full grant detail view.
 * @param {Object} grant - Grant detail from BDNS
 * @returns {string} HTML
 */
export function createGrantDetail(grant) {
  const status = getGrantStatus(grant)
  const days = daysUntilDeadline(grant.fechaFinSolicitud || grant.textFin)
  const urgency = getUrgencyLevel(days)

  return `
    <div class="max-w-3xl mx-auto">
      <!-- Back link -->
      <a href="javascript:history.back()" class="inline-flex items-center gap-1 text-sm text-gray-400
                hover:text-primary transition-colors mb-4 no-underline">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
        </svg>
        Volver
      </a>

      <!-- Title + status -->
      <div class="bg-white rounded-xl border border-gray-100 p-6 mb-4">
        <div class="flex items-start justify-between gap-3 mb-3">
          ${createStatusBadge(status)}
          <span class="text-xs font-mono text-gray-400 bg-gray-50 px-2 py-0.5 rounded">
            BDNS ${escapeHtml(grant.codigoBDNS || '')}
          </span>
        </div>
        <h1 class="text-xl font-bold text-gray-900 mb-2">
          ${escapeHtml(grant.descripcion)}
        </h1>
        ${grant.descripcionLeng ? `
          <p class="text-sm text-gray-500 italic mb-3">
            ${escapeHtml(grant.descripcionLeng)}
          </p>
        ` : ''}
        <p class="text-sm text-gray-500">
          ${escapeHtml(formatConvocante(grant))}
        </p>
      </div>

      <!-- Deadline banner -->
      ${createDeadlineBanner(grant, status, days, urgency)}

      <!-- Quick info grid -->
      ${createInfoGrid(grant)}

      <!-- Application link -->
      ${createApplicationSection(grant, status)}

      <!-- Details sections -->
      ${createBeneficiariesSection(grant)}
      ${createSectorsSection(grant)}
      ${createRegionsSection(grant)}
      ${createDocumentsSection(grant)}
      ${createBasesSection(grant)}
      ${createConcesionesSection(grant)}
      ${createOfficialSourceSection(grant)}
    </div>
  `
}

function formatConvocante(grant) {
  if (!grant.organo) return ''
  const parts = [grant.organo.nivel2, grant.organo.nivel1].filter(Boolean)
  if (grant.organo.nivel3) parts.unshift(grant.organo.nivel3)
  return parts.join(' · ')
}

function createDeadlineBanner(grant, status, days, urgency) {
  if (status === 'closed') {
    return `
      <div class="bg-closed/5 border border-closed/20 rounded-xl p-4 mb-4">
        <p class="text-sm font-medium text-closed">
          Plazo de solicitud finalizado
          ${grant.fechaFinSolicitud ? ` el ${formatDate(grant.fechaFinSolicitud)}` : ''}
        </p>
      </div>
    `
  }

  if (status === 'open' && days != null) {
    const urgencyColors = {
      urgent: 'bg-closed/5 border-closed/20 text-closed',
      warning: 'bg-upcoming/5 border-upcoming/20 text-upcoming',
      normal: 'bg-open/5 border-open/20 text-open',
    }
    const colors = urgencyColors[urgency] || urgencyColors.normal
    return `
      <div class="${colors} border rounded-xl p-4 mb-4">
        <p class="text-sm font-medium">
          ${days === 0 ? 'Ultimo dia para solicitar' :
            days === 1 ? 'Queda 1 dia para solicitar' :
            `Quedan ${days} dias para solicitar`}
          ${grant.fechaFinSolicitud ? ` · Hasta el ${formatDate(grant.fechaFinSolicitud)}` : ''}
        </p>
      </div>
    `
  }

  if (status === 'permanent') {
    return `
      <div class="bg-primary/5 border border-primary/20 rounded-xl p-4 mb-4">
        <p class="text-sm font-medium text-primary">
          Convocatoria abierta permanentemente
        </p>
      </div>
    `
  }

  return ''
}

function createInfoGrid(grant) {
  const items = []

  if (grant.presupuestoTotal) {
    items.push({ label: 'Presupuesto total', value: formatCurrency(grant.presupuestoTotal) })
  }
  if (grant.tipoConvocatoria) {
    items.push({ label: 'Tipo', value: escapeHtml(grant.tipoConvocatoria) })
  }
  if (grant.descripcionFinalidad) {
    items.push({ label: 'Finalidad', value: escapeHtml(grant.descripcionFinalidad) })
  }
  if (grant.fechaRecepcion) {
    items.push({ label: 'Fecha publicacion', value: formatDate(grant.fechaRecepcion) })
  }
  if (grant.fechaInicioSolicitud || grant.textInicio) {
    items.push({
      label: 'Inicio solicitudes',
      value: formatDate(grant.fechaInicioSolicitud) || escapeHtml(grant.textInicio),
    })
  }
  if (grant.fechaFinSolicitud || grant.textFin) {
    items.push({
      label: 'Fin solicitudes',
      value: formatDate(grant.fechaFinSolicitud) || escapeHtml(grant.textFin),
    })
  }

  if (items.length === 0) return ''

  return `
    <div class="bg-white rounded-xl border border-gray-100 p-6 mb-4">
      <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">Informacion general</h2>
      <dl class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        ${items.map((item) => `
          <div>
            <dt class="text-xs text-gray-400 mb-0.5">${item.label}</dt>
            <dd class="text-sm font-medium text-gray-900">${item.value}</dd>
          </div>
        `).join('')}
      </dl>
    </div>
  `
}

function createApplicationSection(grant, status) {
  if (!grant.sedeElectronica && status === 'closed') return ''

  return `
    <div class="bg-white rounded-xl border border-gray-100 p-6 mb-4">
      <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-3">Tramitacion</h2>
      ${grant.sedeElectronica && status !== 'closed' ? `
        <a
          href="${escapeHtml(grant.sedeElectronica)}"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-white font-medium
                 rounded-lg hover:bg-primary-dark transition-colors no-underline text-sm"
        >
          Solicitar en sede electronica
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
          </svg>
        </a>
      ` : `
        <p class="text-sm text-gray-500">No disponible</p>
      `}
    </div>
  `
}

function createBeneficiariesSection(grant) {
  if (!grant.tiposBeneficiarios || grant.tiposBeneficiarios.length === 0) return ''
  return `
    <div class="bg-white rounded-xl border border-gray-100 p-6 mb-4">
      <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-3">Beneficiarios</h2>
      <div class="flex flex-wrap gap-2">
        ${grant.tiposBeneficiarios.map((b) => `
          <span class="px-3 py-1 rounded-full text-xs font-medium bg-primary/5 text-primary">
            ${escapeHtml(typeof b === 'string' ? b : b.descripcion || '')}
          </span>
        `).join('')}
      </div>
    </div>
  `
}

function createSectorsSection(grant) {
  if (!grant.sectores || grant.sectores.length === 0) return ''
  return `
    <div class="bg-white rounded-xl border border-gray-100 p-6 mb-4">
      <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-3">Sectores</h2>
      <div class="flex flex-wrap gap-2">
        ${grant.sectores.map((s) => `
          <span class="px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
            ${escapeHtml(typeof s === 'string' ? s : s.descripcion || '')}
          </span>
        `).join('')}
      </div>
    </div>
  `
}

function createRegionsSection(grant) {
  if (!grant.regiones || grant.regiones.length === 0) return ''
  return `
    <div class="bg-white rounded-xl border border-gray-100 p-6 mb-4">
      <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-3">Regiones</h2>
      <div class="flex flex-wrap gap-2">
        ${grant.regiones.map((r) => `
          <span class="px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
            ${escapeHtml(typeof r === 'string' ? r : r.descripcion || '')}
          </span>
        `).join('')}
      </div>
    </div>
  `
}

function createDocumentsSection(grant) {
  const docs = grant.documentos || []
  if (docs.length === 0) return ''

  const downloadBase = '/api/documentos/'

  return `
    <div class="bg-white rounded-xl border border-gray-100 p-6 mb-4">
      <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-3">Documentos</h2>
      <ul class="space-y-2">
        ${docs.map((d) => `
          <li>
            ${d.id ? `
              <a href="${downloadBase}${encodeURIComponent(d.id)}"
                 target="_blank" rel="noopener noreferrer"
                 class="flex items-center gap-2 text-sm px-3 py-2 rounded-lg bg-gray-50
                        hover:bg-primary/5 text-primary no-underline transition-colors group">
                <svg class="w-4 h-4 text-gray-400 group-hover:text-primary shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                </svg>
                <span class="underline underline-offset-2">${escapeHtml(d.descripcion || d.nombreFic || 'Documento')}</span>
              </a>
            ` : `
              <div class="flex items-center gap-2 text-sm px-3 py-2 rounded-lg bg-gray-50">
                <svg class="w-4 h-4 text-gray-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
                </svg>
                <span class="text-gray-700">${escapeHtml(d.descripcion || d.nombreFic || 'Documento')}</span>
              </div>
            `}
          </li>
        `).join('')}
      </ul>
    </div>
  `
}

function createBasesSection(grant) {
  if (!grant.descripcionBasesReguladoras && !grant.urlBasesReguladoras) return ''

  return `
    <div class="bg-white rounded-xl border border-gray-100 p-6 mb-4">
      <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-3">Bases reguladoras</h2>
      ${grant.descripcionBasesReguladoras ? `
        <p class="text-sm text-gray-700 mb-3">${escapeHtml(grant.descripcionBasesReguladoras)}</p>
      ` : ''}
      ${grant.urlBasesReguladoras ? `
        <a
          href="${escapeHtml(grant.urlBasesReguladoras)}"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-2 px-4 py-2 border border-primary text-primary font-medium
                 rounded-lg hover:bg-primary hover:text-white transition-colors no-underline text-sm"
        >
          Ver bases reguladoras
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
          </svg>
        </a>
      ` : ''}
    </div>
  `
}

function createConcesionesSection(grant) {
  if (!grant.codigoBDNS) return ''
  return `
    <div class="bg-white rounded-xl border border-gray-100 p-6 mb-4">
      <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-3">
        ¿Quien recibio esta ayuda?
      </h2>
      <div id="concesiones-container">
        <button
          id="load-concesiones"
          data-bdns-code="${escapeHtml(grant.codigoBDNS)}"
          class="inline-flex items-center gap-2 px-4 py-2 border border-primary text-primary font-medium
                 rounded-lg hover:bg-primary hover:text-white transition-colors text-sm cursor-pointer"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
          </svg>
          Ver beneficiarios
        </button>
      </div>
    </div>
  `
}

function createOfficialSourceSection(grant) {
  if (!grant.codigoBDNS) return ''

  const officialUrl = `https://www.infosubvenciones.es/bdnstrans/GE/es/convocatoria/${encodeURIComponent(grant.codigoBDNS)}`

  return `
    <div class="bg-white rounded-xl border border-gray-100 p-6 mb-4">
      <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-3">Fuente oficial</h2>
      <p class="text-sm text-gray-700 mb-3">
        Los datos de esta convocatoria provienen de la Base de Datos Nacional de Subvenciones (BDNS).
      </p>
      <a
        href="${officialUrl}"
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex items-center gap-2 px-4 py-2 border border-primary text-primary font-medium
               rounded-lg hover:bg-primary hover:text-white transition-colors no-underline text-sm"
      >
        Ver en infosubvenciones.es (BDNS)
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
        </svg>
      </a>
    </div>
  `
}
