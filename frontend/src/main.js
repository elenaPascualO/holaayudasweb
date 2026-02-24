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
import { renderTransparenciaPage } from './pages/transparencia.js'
import { getGrantDetailCached, getConcesionesByGrant, searchConcesiones, submitFeedback } from './utils/api.js'
import { getGrantStatus } from './utils/dates.js'
import { createStatusBadge } from './components/StatusBadge.js'
import { formatCurrency } from './utils/formatters.js'
import { createConcessionList } from './components/ConcessionCard.js'
import { track, events } from './utils/tracking.js'

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
        <p class="text-xs text-gray-400 mb-3">
          <button id="feedback-toggle" class="text-primary hover:underline cursor-pointer">
            Sugerencias o problemas? Escribenos
          </button>
        </p>
        <div id="feedback-form-wrapper" class="hidden max-w-sm mx-auto mb-4">
          <form id="feedback-form" class="text-left space-y-2">
            <input
              type="email"
              name="email"
              placeholder="Email (opcional)"
              class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg
                     focus:outline-none focus:border-primary"
            />
            <textarea
              name="message"
              required
              maxlength="2000"
              rows="3"
              placeholder="Tu mensaje..."
              class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg
                     focus:outline-none focus:border-primary resize-none"
            ></textarea>
            <div class="flex items-center gap-2">
              <button
                type="submit"
                class="px-4 py-1.5 text-xs font-medium bg-primary text-white rounded-lg
                       hover:bg-primary-dark transition-colors"
              >
                Enviar
              </button>
              <span id="feedback-status" class="text-xs text-gray-400"></span>
            </div>
          </form>
        </div>
        <p class="text-xs text-gray-400">
          Los resultados se obtienen en tiempo real de
          <a href="https://www.infosubvenciones.es" target="_blank" rel="noopener noreferrer"
             class="text-gray-500 hover:text-primary">infosubvenciones.es</a>
          (BDNS).
        </p>
        <p class="text-xs text-gray-400 mt-0.5">
          Hola Ayudas es solo una interfaz mas amigable para consultar los datos oficiales.
        </p>
        <p class="text-xs text-gray-300 mt-1">
          Un proyecto de HolaDatos ·
          <a href="https://x.com/hola_datos_es" target="_blank" rel="noopener noreferrer"
             class="text-gray-400 hover:text-primary">X</a>
          ·
          <a href="https://www.linkedin.com/company/hola-datos/" target="_blank" rel="noopener noreferrer"
             class="text-gray-400 hover:text-primary">LinkedIn</a>
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
  const transparenciaForm = document.getElementById('transparencia-filters')
  if (transparenciaForm) {
    transparenciaForm.addEventListener('submit', handleTransparenciaFilter)
  }

  // Beneficiary drill-down (expand concesiones)
  app.querySelectorAll('[data-expand-beneficiary]').forEach((row) => {
    row.addEventListener('click', handleBeneficiaryDrillDown)
  })

  // Feedback form toggle
  const feedbackToggle = document.getElementById('feedback-toggle')
  if (feedbackToggle) {
    feedbackToggle.addEventListener('click', () => {
      const wrapper = document.getElementById('feedback-form-wrapper')
      if (wrapper) {
        const wasHidden = wrapper.classList.contains('hidden')
        wrapper.classList.toggle('hidden')
        if (wasHidden) track(events.FEEDBACK_OPEN)
      }
    })
  }

  // Feedback form submission
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
      } else if (href.includes('idDocumento')) {
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

  try {
    const data = await getConcesionesByGrant(bdnsCode, 0, 20)
    const items = data.content || []

    if (items.length === 0) {
      container.innerHTML = `
        <div class="text-sm text-gray-400 space-y-1">
          <p>No constan concesiones en la BDNS para esta convocatoria.</p>
          <p class="text-xs">Esto puede deberse a que la ayuda aun no se ha resuelto, no fue concedida, o las concesiones no se registraron en el sistema.</p>
        </div>
      `
      return
    }

    let html = createConcessionList(items)

    // Show total count
    const total = data.totalElements || items.length
    html = `
      <p class="text-xs text-gray-400 mb-2">${total} beneficiario${total !== 1 ? 's' : ''} registrado${total !== 1 ? 's' : ''}</p>
      ${html}
    `

    // Load more button if there are more pages
    if (data.totalPages > 1) {
      html += `
        <button
          id="load-more-concesiones"
          data-bdns-code="${bdnsCode}"
          data-next-page="1"
          data-total-pages="${data.totalPages}"
          class="mt-3 w-full py-2 text-sm font-medium text-primary border border-primary/30
                 rounded-lg hover:bg-primary/5 transition-colors cursor-pointer"
        >
          Ver mas beneficiarios
        </button>
      `
    }

    container.innerHTML = html

    // Wire up "load more" if present
    const loadMoreBtn = document.getElementById('load-more-concesiones')
    if (loadMoreBtn) {
      loadMoreBtn.addEventListener('click', handleLoadMoreConcesiones)
    }
  } catch {
    container.innerHTML = `
      <p class="text-sm text-gray-400">Error al cargar las concesiones. Intentalo de nuevo.</p>
    `
  }
}

/**
 * Handle "Ver mas beneficiarios" — load next page of concesiones.
 */
async function handleLoadMoreConcesiones(e) {
  const btn = e.currentTarget
  const bdnsCode = btn.dataset.bdnsCode
  const nextPage = parseInt(btn.dataset.nextPage, 10)
  const totalPages = parseInt(btn.dataset.totalPages, 10)

  btn.disabled = true
  btn.textContent = 'Cargando...'

  try {
    const data = await getConcesionesByGrant(bdnsCode, nextPage, 20)
    const items = data.content || []

    if (items.length > 0) {
      // Insert new items before the button
      const listHtml = createConcessionList(items)
      btn.insertAdjacentHTML('beforebegin', listHtml)
    }

    // Update or remove the button
    if (nextPage + 1 >= totalPages) {
      btn.remove()
    } else {
      btn.dataset.nextPage = String(nextPage + 1)
      btn.disabled = false
      btn.textContent = 'Ver mas beneficiarios'
    }
  } catch {
    btn.disabled = false
    btn.textContent = 'Error — Reintentar'
  }
}

/**
 * Handle transparencia filter form submission.
 */
function handleTransparenciaFilter(e) {
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

  track(events.TRANSPARENCIA_FILTER, { anio: anio || '', nifCif: nifCif || '', q: q || '' })
  navigate(`/transparencia?${params.toString()}`)
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
  track(events.TRANSPARENCIA_DRILL_DOWN, { nifCif })

  // Read year filter from the ranking container to scope concesiones
  const rankingEl = document.getElementById('beneficiarios-ranking')
  const anio = rankingEl?.dataset.anio || ''
  const concesionesParams = { nifCif, page: 0, pageSize: 20 }
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

    // Sort by amount descending
    items.sort((a, b) => (b.importe || 0) - (a.importe || 0))

    const total = data.totalElements || items.length
    let html = `<p class="text-xs text-gray-400 mb-2">${total} concesion${total !== 1 ? 'es' : ''}</p>`
    html += createConcessionList(items, { showConvocatoria: true })
    container.innerHTML = html
  } catch {
    container.innerHTML = `
      <p class="text-sm text-gray-400 py-2">Error al cargar concesiones.</p>
    `
  }
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
  enrichVisibleCards()
})

registerRoute('/buscar', async (params) => {
  renderLoading()
  const html = await renderSearchPage(params)
  render(html)
  enrichVisibleCards()
})

registerRoute('/transparencia', async (params) => {
  renderLoading()
  const html = await renderTransparenciaPage(params)
  render(html)
  track(events.TRANSPARENCIA_VIEW, { anio: params.anio || '' })
})

registerRoute('/ayuda/:bdnsCode', async (params) => {
  renderLoading()
  const html = await renderDetailPage(params.bdnsCode)
  render(html)
  track(events.DETAIL_VIEW, { bdns: params.bdnsCode })
})

// --- Start ---
initRouter()
