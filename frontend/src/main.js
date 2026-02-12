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
          Un proyecto de
          <a href="https://holadatos.com" target="_blank" rel="noopener noreferrer"
             class="text-gray-400 hover:text-primary">HolaDatos</a>
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
 * Handle filter form submission.
 */
function handleFilterSubmit(e) {
  e.preventDefault()
  const formData = new FormData(e.target)
  const params = new URLSearchParams()

  // Preserve the current search query
  const currentParams = new URLSearchParams(window.location.search)
  const q = currentParams.get('q')
  if (q) params.set('q', q)

  // Add filter values
  const tipo = formData.get('tipoAdministracion')
  if (tipo) params.set('tipoAdministracion', tipo)

  const fechaDesde = formData.get('fechaDesde')
  if (fechaDesde) params.set('fechaDesde', fechaDesde)

  const fechaHasta = formData.get('fechaHasta')
  if (fechaHasta) params.set('fechaHasta', fechaHasta)

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

// --- Register routes ---

registerRoute('/', async () => {
  renderLoading()
  const html = await renderHomePage()
  render(html)
})

registerRoute('/buscar', async (params) => {
  renderLoading()
  const html = await renderSearchPage(params)
  render(html)
})

registerRoute('/ayuda/:bdnsCode', async (params) => {
  renderLoading()
  const html = await renderDetailPage(params.bdnsCode)
  render(html)
})

// --- Start ---
initRouter()
