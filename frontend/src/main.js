/**
 * Hola Ayudas - Main entry point.
 *
 * Wires together the router, pages, and event handlers.
 */

import './style.css'
import { initRouter, registerRoute, navigate } from './router.js'
import { createHeader } from './components/Header.js'
import { createLoadingSpinner } from './components/LoadingSpinner.js'
import { renderHomePage } from './pages/home.js'
import { renderSearchPage } from './pages/search.js'
import { renderDetailPage } from './pages/detail.js'
import { renderTransparenciaPage } from './pages/beneficiarios.js'
import { renderConcesionesPage } from './pages/concesiones.js'
import { renderContactoPage } from './pages/contacto.js'
import { renderAnalyticsPage, initAnalyticsCharts, initKeywordTrend } from './pages/analytics.js'
import { getGrantDetailCached, getConcesionesCount, searchConcesiones, submitFeedback } from './utils/api.js'
import { getGrantStatus } from './utils/dates.js'
import { createStatusBadge } from './components/StatusBadge.js'
import { formatCurrency } from './utils/formatters.js'
import { createConcessionList } from './components/ConcessionCard.js'
import { track, events } from './utils/tracking.js'
import { updateMetaTags, buildBreadcrumbSchema, buildGrantSchema } from './utils/seo.js'

const app = document.querySelector('#app')

/**
 * Render a page with the header wrapper.
 * @param {string} pageHtml - Page content HTML
 */
function render(pageHtml) {
  app.innerHTML =
    createHeader() +
    `<main class="max-w-5xl mx-auto px-4 py-6">${pageHtml}</main>` +
    createFooter()
  setupEventListeners()
}

/**
 * Show loading state.
 */
function renderLoading() {
  render(createLoadingSpinner())
}

/**
 * Create the footer.
 */
function createFooter() {
  return `
    <footer class="border-t border-gray-100 mt-12 py-6">
      <div class="max-w-5xl mx-auto px-4 text-center">
        <p class="text-xs text-gray-400">
          Los datos no se consultan en tiempo real. La base de datos de Hola Ayudas se sincroniza diariamente con la
          <a href="https://www.infosubvenciones.es" target="_blank" rel="noopener noreferrer"
             class="text-gray-500 hover:text-primary">BDNS</a>
          para ofrecer busqueda inteligente y estadisticas.
        </p>
        <p class="text-xs text-gray-300 mt-1">
          Un proyecto de
          <a href="/contacto" data-link class="text-gray-400 hover:text-primary no-underline">HolaDatos</a>
          ·
          <a href="/contacto" data-link class="text-gray-400 hover:text-primary no-underline">Contacto</a>
        </p>
      </div>
    </footer>
  `
}

/**
 * Set up event delegation for all interactive elements.
 */
function setupEventListeners() {
  // SPA navigation via data-link attributes
  app.addEventListener('click', handleLinkClick)

  // Search form submission
  const searchForm = document.getElementById('search-form')
  if (searchForm) {
    searchForm.addEventListener('submit', handleSearchSubmit)
  }

  // Quick filter chips
  app.querySelectorAll('[data-filter]').forEach((chip) => {
    chip.addEventListener('click', handleQuickFilter)
  })

  // Filter form submission
  const filterForm = document.getElementById('filter-form')
  if (filterForm) {
    filterForm.addEventListener('submit', handleFilterSubmit)
  }

  // Clear filters
  const clearBtn = document.getElementById('clear-filters')
  if (clearBtn) {
    clearBtn.addEventListener('click', handleClearFilters)
  }

  // Region dropdown visibility based on admin type selection
  const adminRadios = app.querySelectorAll('[name="tipoAdministracion"]')
  adminRadios.forEach((radio) => {
    radio.addEventListener('change', handleAdminTypeChange)
  })

  // Sort selector
  const sortSelect = document.getElementById('sort-select')
  if (sortSelect) {
    sortSelect.addEventListener('change', handleSortChange)
  }

  // Load concesiones button
  const loadConcesionesBtn = document.getElementById('load-concesiones')
  if (loadConcesionesBtn) {
    loadConcesionesBtn.addEventListener('click', handleLoadConcesiones)
  }

  // Transparencia filter form
  const beneficiariosForm = document.getElementById('beneficiarios-filters')
  if (beneficiariosForm) {
    beneficiariosForm.addEventListener('submit', handleBeneficiariosFilter)
  }

  // Beneficiary drill-down (expand concesiones)
  app.querySelectorAll('[data-expand-beneficiary]').forEach((row) => {
    row.addEventListener('click', handleBeneficiaryDrillDown)
  })

  // Semantic search filter form
  const semanticFilterForm = document.getElementById('semantic-filter-form')
  if (semanticFilterForm) {
    semanticFilterForm.addEventListener('submit', handleSemanticFilterSubmit)
  }

  // Clear semantic filters
  const clearSemanticBtn = document.getElementById('clear-semantic-filters')
  if (clearSemanticBtn) {
    clearSemanticBtn.addEventListener('click', handleClearSemanticFilters)
  }

  // Feedback form submission (on contact page)
  const feedbackForm = document.getElementById('feedback-form')
  if (feedbackForm) {
    feedbackForm.addEventListener('submit', handleFeedbackSubmit)
  }

  // Track detail page external link clicks
  app.querySelectorAll('a[target="_blank"]').forEach((link) => {
    link.addEventListener('click', () => {
      const href = link.getAttribute('href') || ''
      const text = link.textContent.toLowerCase()
      if (text.includes('solicitar en sede')) {
        track(events.DETAIL_APPLY)
      } else if (href.includes('/api/documentos/') || href.includes('idDocumento')) {
        track(events.DETAIL_DOCUMENT)
      } else if (text.includes('bases reguladoras')) {
        track(events.DETAIL_BASES)
      } else if (href.includes('infosubvenciones.es/bdnstrans/GE')) {
        track(events.DETAIL_OFFICIAL)
      }
    })
  })
}

/**
 * Handle clicks on elements with data-link attribute for SPA navigation.
 */
function handleLinkClick(e) {
  const link = e.target.closest('[data-link]')
  if (!link) return
  e.preventDefault()
  const path = link.getAttribute('data-link') || link.getAttribute('href')
  if (!path || path === '#') return

  // Track pagination clicks
  if (path.includes('page=')) {
    const pageMatch = path.match(/page=(\d+)/)
    track(events.PAGINATION, { page: pageMatch ? parseInt(pageMatch[1], 10) + 1 : 0 })
  }

  navigate(path)
}

/**
 * Handle search form submission.
 */
function handleSearchSubmit(e) {
  e.preventDefault()
  const input = document.getElementById('search-input')
  const q = input?.value.trim()
  track(events.SEARCH_SUBMIT, { query: q || '(empty)' })
  if (q) {
    navigate(`/buscar?q=${encodeURIComponent(q)}`)
  } else {
    navigate('/buscar')
  }
}

/**
 * Handle quick filter chip clicks.
 */
function handleQuickFilter(e) {
  const query = e.currentTarget.dataset.filter
  if (query) {
    track(events.QUICK_FILTER, { filter: query })
    navigate(`/buscar?q=${encodeURIComponent(query)}`)
  }
}

/**
 * Handle admin type radio change — show/hide the corresponding region dropdown.
 */
function handleAdminTypeChange(e) {
  const tipo = e.target.value
  const commWrapper = document.getElementById('region-communities-wrapper')
  const provWrapper = document.getElementById('region-provinces-wrapper')

  if (commWrapper) {
    commWrapper.classList.toggle('hidden', tipo !== 'A')
    if (tipo !== 'A') {
      const sel = document.getElementById('region-communities')
      if (sel) sel.value = ''
    }
  }

  if (provWrapper) {
    provWrapper.classList.toggle('hidden', tipo !== 'L')
    if (tipo !== 'L') {
      const sel = document.getElementById('region-provinces')
      if (sel) sel.value = ''
    }
  }
}

/**
 * Handle filter form submission.
 */
function handleFilterSubmit(e) {
  e.preventDefault()
  const formData = new FormData(e.target)
  const params = new URLSearchParams()

  // Track filter usage
  const activeFilters = ['estado', 'tipoAdministracion', 'fechaDesdeYear', 'fechaHastaYear']
    .filter((k) => formData.get(k))
    .map((k) => k.replace('Year', ''))
  track(events.FILTER_APPLY, { filters: activeFilters.join(',') || 'none' })

  // Read search query from the input (not URL) so clearing it works
  const searchInput = document.getElementById('search-input')
  const q = searchInput?.value.trim()
  if (q) params.set('q', q)

  // Add filter values
  const estado = formData.get('estado')
  if (estado) params.set('estado', estado)

  const tipo = formData.get('tipoAdministracion')
  if (tipo) params.set('tipoAdministracion', tipo)

  // Read region from the active dropdown
  let regiones = ''
  if (tipo === 'A') regiones = document.getElementById('region-communities')?.value || ''
  if (tipo === 'L') regiones = document.getElementById('region-provinces')?.value || ''
  if (regiones) params.set('regiones', regiones)

  // Advanced catalog filters
  const instrumentos = formData.get('instrumentos')
  if (instrumentos) params.set('instrumentos', instrumentos)

  const tiposBeneficiario = formData.get('tiposBeneficiario')
  if (tiposBeneficiario) params.set('tiposBeneficiario', tiposBeneficiario)

  const finalidad = formData.get('finalidad')
  if (finalidad) params.set('finalidad', finalidad)

  // Preserve sort order
  const currentParams = new URLSearchParams(window.location.search)
  const orden = currentParams.get('orden')
  if (orden) params.set('orden', orden)

  // Build date params from year+month selects
  const desdeYear = formData.get('fechaDesdeYear')
  if (desdeYear) {
    const desdeMonth = formData.get('fechaDesdeMonth') || '1'
    params.set('fechaDesde', `${desdeYear}-${String(desdeMonth).padStart(2, '0')}-01`)
  }

  const hastaYear = formData.get('fechaHastaYear')
  if (hastaYear) {
    const hastaMonth = formData.get('fechaHastaMonth') || '12'
    const lastDay = new Date(hastaYear, hastaMonth, 0).getDate()
    params.set('fechaHasta', `${hastaYear}-${String(hastaMonth).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`)
  }

  navigate(`/buscar?${params.toString()}`)
}

/**
 * Handle sort order change.
 */
function handleSortChange(e) {
  const params = new URLSearchParams(window.location.search)
  const orden = e.target.value
  track(events.SORT_CHANGE, { order: orden })
  if (orden === 'asc') {
    params.set('orden', orden)
  } else {
    params.delete('orden')
  }
  params.delete('page')
  navigate(`/buscar?${params.toString()}`)
}

/**
 * Handle feedback form submission.
 */
async function handleFeedbackSubmit(e) {
  e.preventDefault()
  const form = e.target
  const status = document.getElementById('feedback-status')
  const btn = form.querySelector('button[type="submit"]')

  btn.disabled = true
  btn.textContent = 'Enviando...'
  if (status) status.textContent = ''

  track(events.FEEDBACK_SUBMIT)

  try {
    await submitFeedback({
      email: form.email.value.trim(),
      message: form.message.value.trim(),
    })
    form.reset()
    if (status) {
      status.textContent = 'Mensaje enviado, gracias!'
      status.className = 'text-xs text-open'
    }
    setTimeout(() => {
      const wrapper = document.getElementById('feedback-form-wrapper')
      if (wrapper) wrapper.classList.add('hidden')
      if (status) { status.textContent = ''; status.className = 'text-xs text-gray-400' }
    }, 3000)
  } catch {
    if (status) {
      status.textContent = 'Error al enviar. Intentalo de nuevo.'
      status.className = 'text-xs text-closed'
    }
  } finally {
    btn.disabled = false
    btn.textContent = 'Enviar'
  }
}

/**
 * Handle "Ver beneficiarios" button click — load concesiones for a grant.
 */
async function handleLoadConcesiones(e) {
  const btn = e.currentTarget
  const bdnsCode = btn.dataset.bdnsCode
  if (!bdnsCode) return

  const container = document.getElementById('concesiones-container')
  if (!container) return

  btn.disabled = true
  btn.textContent = 'Cargando...'
  track(events.CONCESIONES_VIEW, { bdns: bdnsCode })

  const officialUrl = `https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias/${encodeURIComponent(bdnsCode)}/concesiones`

  // Quick probe with pageSize=1 and 8s timeout to detect massive datasets
  try {
    const probe = await getConcesionesCount(bdnsCode, 8000)
    const total = probe.totalElements || 0

    if (total === 0) {
      container.innerHTML = `
        <div class="text-sm text-gray-400 space-y-1">
          <p>No constan concesiones en la BDNS para esta convocatoria.</p>
          <p class="text-xs">Esto puede deberse a que la ayuda aun no se ha resuelto, no fue concedida, o las concesiones no se registraron en el sistema.</p>
        </div>
      `
      return
    }

    // Too many individual beneficiaries — show count + official link instead of list
    if (total > 10000) {
      container.innerHTML = `
        <div class="text-sm space-y-2">
          <p class="text-gray-500">
            Esta convocatoria tiene <strong>${total.toLocaleString('es-ES')}</strong> beneficiarios individuales registrados.
            Debido al volumen, no es posible mostrar el listado completo aqui.
          </p>
          <a href="${officialUrl}" target="_blank" rel="noopener noreferrer"
             class="inline-flex items-center gap-2 px-4 py-2 border border-primary text-primary font-medium
                    rounded-lg hover:bg-primary hover:text-white transition-colors no-underline text-sm">
            Consultar listado en la web oficial
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
            </svg>
          </a>
        </div>
      `
      return
    }
  } catch {
    // Probe failed or timed out — assume massive dataset, redirect to official
    container.innerHTML = `
      <div class="text-sm space-y-2">
        <p class="text-gray-500">
          No se pudo obtener el listado de beneficiarios. Es posible que esta convocatoria tenga
          un volumen muy elevado de concesiones y el servidor de la BDNS no pueda responder a tiempo.
        </p>
        <a href="${officialUrl}" target="_blank" rel="noopener noreferrer"
           class="inline-flex items-center gap-2 px-4 py-2 border border-primary text-primary font-medium
                  rounded-lg hover:bg-primary hover:text-white transition-colors no-underline text-sm">
          Consultar listado en la web oficial
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
          </svg>
        </a>
        <button
          id="retry-concesiones"
          data-bdns-code="${bdnsCode}"
          class="inline-flex items-center gap-2 px-4 py-2 border border-primary text-primary font-medium
                 rounded-lg hover:bg-primary hover:text-white transition-colors text-sm cursor-pointer"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          Reintentar
        </button>
      </div>
    `
    const retryBtn = document.getElementById('retry-concesiones')
    if (retryBtn) {
      retryBtn.addEventListener('click', handleLoadConcesiones)
    }
    return
  }

  // Probe passed and total <= 10000 — load top 10 by amount
  btn.textContent = 'Cargando beneficiarios...'
  const slowTimer = setTimeout(() => {
    const slowMsg = document.getElementById('concesiones-slow-msg')
    if (!slowMsg) {
      btn.insertAdjacentHTML('afterend', `
        <p id="concesiones-slow-msg" class="text-xs text-amber-600 mt-2">
          La BDNS esta tardando en responder. Esto es normal cuando hay muchos beneficiarios, ten paciencia...
        </p>
      `)
    }
  }, 4000)

  try {
    const data = await searchConcesiones({ bdnsCode, page: 0, pageSize: 10, order: 'importe', direccion: 'desc' })
    clearTimeout(slowTimer)
    const items = data.content || []
    const total = data.totalElements || items.length

    let html = `
      <p class="text-xs text-gray-400 mb-2">${total} beneficiario${total !== 1 ? 's' : ''} registrado${total !== 1 ? 's' : ''}</p>
    `
    html += createConcessionList(items)

    // "Ver todos" link to full paginated page when there are more than shown
    if (total > 10) {
      html += `
        <a href="/concesiones?bdnsCode=${encodeURIComponent(bdnsCode)}" data-link
           class="mt-3 w-full py-2 text-sm font-medium text-primary border border-primary/30
                  rounded-lg hover:bg-primary/5 transition-colors cursor-pointer flex items-center justify-center gap-1 no-underline">
          Ver todos los ${total.toLocaleString('es-ES')} beneficiarios
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </a>
      `
    }

    container.innerHTML = html
  } catch {
    clearTimeout(slowTimer)
    container.innerHTML = `
      <div class="text-sm space-y-2">
        <p class="text-gray-500">No se pudieron cargar los beneficiarios. Esto suele deberse a que el servidor de la BDNS (infosubvenciones.es) tarda en responder.</p>
        <button
          id="retry-concesiones"
          data-bdns-code="${bdnsCode}"
          class="inline-flex items-center gap-2 px-4 py-2 border border-primary text-primary font-medium
                 rounded-lg hover:bg-primary hover:text-white transition-colors text-sm cursor-pointer"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          Reintentar
        </button>
      </div>
    `
    const retryBtn = document.getElementById('retry-concesiones')
    if (retryBtn) {
      retryBtn.addEventListener('click', handleLoadConcesiones)
    }
  }
}

/**
 * Handle transparencia filter form submission.
 */
function handleBeneficiariosFilter(e) {
  e.preventDefault()
  const formData = new FormData(e.target)
  const params = new URLSearchParams()

  const q = formData.get('q')?.trim()
  if (q) params.set('q', q)

  const anio = formData.get('anio')
  if (anio) {
    params.set('anio', anio)
  } else {
    params.set('anio', 'todos')
  }

  const nifCif = formData.get('nifCif')?.trim()
  if (nifCif) params.set('nifCif', nifCif)

  track(events.BENEFICIARIOS_FILTER, { anio: anio || '', nifCif: nifCif || '', q: q || '' })
  navigate(`/beneficiarios?${params.toString()}`)
}

/**
 * Handle beneficiary row click — toggle concesiones drill-down.
 */
async function handleBeneficiaryDrillDown(e) {
  const row = e.currentTarget
  const nifCif = row.dataset.expandBeneficiary
  if (!nifCif) return

  const parentRow = row.closest('.beneficiary-row')
  if (!parentRow) return

  const container = parentRow.querySelector('.concesiones-container')
  if (!container) return

  const icon = row.querySelector('.expand-icon')

  // Toggle: if already visible, collapse
  if (!container.classList.contains('hidden')) {
    container.classList.add('hidden')
    container.innerHTML = ''
    if (icon) icon.style.transform = ''
    return
  }

  // Expand
  container.classList.remove('hidden')
  if (icon) icon.style.transform = 'rotate(180deg)'
  container.innerHTML = createLoadingSpinner()
  track(events.BENEFICIARIOS_DRILL_DOWN, { nifCif })

  // Read year filter from the ranking container to scope concesiones
  const rankingEl = document.getElementById('beneficiarios-ranking')
  const anio = rankingEl?.dataset.anio || ''
  const concesionesParams = { nifCif, page: 0, pageSize: 5, order: 'importe', direccion: 'desc' }
  if (anio) {
    concesionesParams.fechaDesde = `${anio}-01-01`
    concesionesParams.fechaHasta = `${anio}-12-31`
  }

  try {
    const data = await searchConcesiones(concesionesParams)
    const items = data.content || []

    if (items.length === 0) {
      container.innerHTML = `
        <p class="text-sm text-gray-400 py-2">No se encontraron concesiones individuales para este beneficiario.</p>
      `
      return
    }

    const total = data.totalElements || items.length
    let html = `<p class="text-xs text-gray-400 mb-2">${total} concesion${total !== 1 ? 'es' : ''}</p>`
    html += createConcessionList(items, { showConvocatoria: true })

    // "Ver todas" link when there are more than 5
    if (total > 5) {
      const linkParams = new URLSearchParams({ nifCif })
      if (anio) linkParams.set('anio', anio)
      // Preserve current transparencia URL so user can return to same state
      const returnTo = window.location.pathname + window.location.search
      linkParams.set('returnTo', returnTo)
      html += `
        <a href="/concesiones?${linkParams.toString()}" data-link
           class="inline-flex items-center gap-1 mt-3 text-sm font-medium text-primary hover:underline no-underline">
          Ver todas las ${total} concesiones
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </a>
      `
    }

    container.innerHTML = html
  } catch {
    container.innerHTML = `
      <p class="text-sm text-gray-400 py-2">Error al cargar concesiones.</p>
    `
  }
}

/**
 * Handle semantic filter form submission.
 */
function handleSemanticFilterSubmit(e) {
  e.preventDefault()
  const formData = new FormData(e.target)
  const currentParams = new URLSearchParams(window.location.search)
  const params = new URLSearchParams()

  // Preserve search query
  const searchInput = document.getElementById('search-input')
  const q = searchInput?.value.trim()
  if (q) params.set('q', q)

  const yearFrom = formData.get('yearFrom')
  if (yearFrom) params.set('yearFrom', yearFrom)

  const yearTo = formData.get('yearTo')
  if (yearTo) params.set('yearTo', yearTo)

  const abierto = formData.get('abierto')
  if (abierto) params.set('abierto', abierto)

  // Map abierto (true/false) to estado (abiertas/cerradas) for non-semantic search
  if (abierto === 'true') params.set('estado', 'abiertas')
  else if (abierto === 'false') params.set('estado', 'cerradas')
  // If no abierto set, preserve existing estado from URL
  else if (currentParams.get('estado')) params.set('estado', currentParams.get('estado'))

  // Preserve analytics drill-down params from current URL
  for (const key of ['descripcionFinalidad', 'regionDesc']) {
    const val = currentParams.get(key)
    if (val) params.set(key, val)
  }

  navigate(`/buscar?${params.toString()}`)
}

/**
 * Handle clear semantic filters.
 */
function handleClearSemanticFilters() {
  const currentParams = new URLSearchParams(window.location.search)
  const q = currentParams.get('q')
  navigate(q ? `/buscar?q=${encodeURIComponent(q)}` : '/buscar')
}

/**
 * Handle clear filters button.
 */
function handleClearFilters() {
  track(events.FILTER_CLEAR)
  const currentParams = new URLSearchParams(window.location.search)
  const q = currentParams.get('q')
  navigate(q ? `/buscar?q=${encodeURIComponent(q)}` : '/buscar')
}

/**
 * Enrich visible grant cards with detail data (status badge + budget).
 * Fetches details in parallel with limited concurrency.
 */
function enrichVisibleCards() {
  const badges = app.querySelectorAll('[data-grant-badge]')
  if (badges.length === 0) return

  // Skip cards already enriched by the backend
  const codes = [...new Set(
    [...badges]
      .filter((el) => !el.closest('[data-enriched]'))
      .map((el) => el.dataset.grantBadge)
  )]
  if (codes.length === 0) return
  const MAX_CONCURRENT = 2
  let index = 0

  function updateCard(code, detail) {
    const status = getGrantStatus(detail)
    const badgeEl = app.querySelector(`[data-grant-badge="${code}"]`)
    if (badgeEl) badgeEl.innerHTML = createStatusBadge(status)

    const budgetEl = app.querySelector(`[data-grant-budget="${code}"]`)
    if (budgetEl && detail.presupuestoTotal) {
      budgetEl.classList.add('inline-flex', 'items-center', 'px-2.5', 'py-0.5', 'rounded-full', 'text-xs', 'font-semibold', 'bg-blue-50', 'text-blue-700')
      budgetEl.textContent = formatCurrency(detail.presupuestoTotal)
    }
  }

  function next() {
    if (index >= codes.length) return
    const code = codes[index++]
    getGrantDetailCached(code)
      .then((detail) => updateCard(code, detail))
      .catch(() => {})
      .finally(next)
  }

  for (let i = 0; i < Math.min(MAX_CONCURRENT, codes.length); i++) {
    next()
  }
}

// --- Register routes ---

registerRoute('/', async (params) => {
  renderLoading()
  const html = await renderHomePage(params)
  render(html)
  updateMetaTags({ path: '/' })
  enrichVisibleCards()
})

registerRoute('/buscar', async (params) => {
  renderLoading()
  const html = await renderSearchPage(params)
  render(html)
  const q = new URLSearchParams(window.location.search).get('q')
  updateMetaTags({
    title: q ? `Resultados: ${q}` : 'Buscar ayudas y subvenciones',
    description: q
      ? `Resultados de busqueda para "${q}" en ayudas y subvenciones publicas de España.`
      : 'Busca ayudas y subvenciones publicas en España. Filtra por tipo, region, fecha y mas.',
    path: '/buscar',
  })
  enrichVisibleCards()
})

registerRoute('/beneficiarios', async (params) => {
  renderLoading()
  const html = await renderTransparenciaPage(params)
  render(html)
  updateMetaTags({
    title: 'Beneficiarios - Mayores receptores de subvenciones',
    description: 'Ranking de los mayores beneficiarios de subvenciones publicas en España. Consulta quien recibe mas fondos publicos.',
    path: '/beneficiarios',
  })
  track(events.BENEFICIARIOS_VIEW, { anio: params.anio || '' })
})

registerRoute('/concesiones', async (params) => {
  renderLoading()
  const html = await renderConcesionesPage(params)
  render(html)
  updateMetaTags({
    title: 'Concesiones de subvenciones',
    description: 'Listado de concesiones de subvenciones publicas otorgadas en España.',
    path: '/concesiones',
  })
  track(events.CONCESIONES_VIEW, { nifCif: params.nifCif || '' })
})

registerRoute('/ayuda/:bdnsCode', async (params) => {
  renderLoading()
  const html = await renderDetailPage(params.bdnsCode)
  render(html)

  // Set SEO meta tags from cached grant data (already fetched by renderDetailPage)
  try {
    const grant = await getGrantDetailCached(params.bdnsCode)
    const orgName = [grant.organo?.nivel3, grant.organo?.nivel2, grant.organo?.nivel1]
      .filter(Boolean).join(' - ')
    const descText = (grant.descripcion || '').slice(0, 160)

    updateMetaTags({
      title: grant.descripcion || `Ayuda ${params.bdnsCode}`,
      description: `${descText}${orgName ? ` — ${orgName}` : ''}`,
      path: `/ayuda/${params.bdnsCode}`,
      jsonLd: [
        buildGrantSchema(grant),
        buildBreadcrumbSchema([
          { name: 'Inicio', url: 'https://www.holaayudas.com/' },
          { name: 'Buscar', url: 'https://www.holaayudas.com/buscar' },
          { name: grant.descripcion || `Ayuda ${params.bdnsCode}`, url: `https://www.holaayudas.com/ayuda/${params.bdnsCode}` },
        ]),
      ],
    })
  } catch {
    updateMetaTags({
      title: `Ayuda ${params.bdnsCode}`,
      path: `/ayuda/${params.bdnsCode}`,
    })
  }

  track(events.DETAIL_VIEW, { bdns: params.bdnsCode })
})

registerRoute('/estadisticas', async (params) => {
  renderLoading()
  const html = await renderAnalyticsPage(params)
  render(html)
  updateMetaTags({
    title: 'Datos y estadisticas de subvenciones publicas',
    description: 'Dashboard con datos y estadisticas de subvenciones publicas en España. Tendencias, presupuestos, regiones y tematicas.',
    path: '/estadisticas',
  })
  initAnalyticsCharts()
  initKeywordTrend()
})

registerRoute('/contacto', () => {
  const html = renderContactoPage()
  render(html)
  updateMetaTags({
    title: 'Contacto',
    description: 'Contacta con el equipo de Hola Ayudas. Sugerencias, errores o colaboraciones.',
    path: '/contacto',
  })
})

// --- Start ---
initRouter()
