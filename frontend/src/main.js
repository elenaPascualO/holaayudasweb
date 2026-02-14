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
import { getGrantDetailCached } from './utils/api.js'
import { getGrantStatus } from './utils/dates.js'
import { createStatusBadge } from './components/StatusBadge.js'
import { formatCurrency } from './utils/formatters.js'

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
          Hola Ayudas · Datos de
          <a href="https://www.infosubvenciones.es" target="_blank" rel="noopener noreferrer"
             class="text-gray-500 hover:text-primary">infosubvenciones.es</a>
          (BDNS)
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
}

/**
 * Handle clicks on elements with data-link attribute for SPA navigation.
 */
function handleLinkClick(e) {
  const link = e.target.closest('[data-link]')
  if (!link) return
  e.preventDefault()
  const path = link.getAttribute('data-link') || link.getAttribute('href')
  if (path && path !== '#') navigate(path)
}

/**
 * Handle search form submission.
 */
function handleSearchSubmit(e) {
  e.preventDefault()
  const input = document.getElementById('search-input')
  const q = input?.value.trim()
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
  if (orden === 'asc') {
    params.set('orden', orden)
  } else {
    params.delete('orden')
  }
  params.delete('page')
  navigate(`/buscar?${params.toString()}`)
}

/**
 * Handle clear filters button.
 */
function handleClearFilters() {
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
  const MAX_CONCURRENT = 5
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

registerRoute('/', async () => {
  renderLoading()
  const html = await renderHomePage()
  render(html)
  enrichVisibleCards()
})

registerRoute('/buscar', async (params) => {
  renderLoading()
  const html = await renderSearchPage(params)
  render(html)
  enrichVisibleCards()
})

registerRoute('/ayuda/:bdnsCode', async (params) => {
  renderLoading()
  const html = await renderDetailPage(params.bdnsCode)
  render(html)
})

// --- Start ---
initRouter()
