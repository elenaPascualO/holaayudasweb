/**
 * Analytics dashboard page — grant data insights with Chart.js.
 */

import {
  fetchAnalyticsSummary,
  fetchAnalyticsByYear,
  fetchAnalyticsByTheme,
  fetchAnalyticsByRegion,
  fetchAnalyticsTopOrgans,
  fetchAnalyticsStatus,
  fetchKeywordTrend,
  searchTopBeneficiaries,
  semanticSearch,
} from '../utils/api.js'
import { formatNumber, formatCurrency } from '../utils/formatters.js'
import { navigate } from '../router.js'
import { createGrantCard } from '../components/GrantCard.js'
import { createBeneficiaryList } from '../components/BeneficiaryRow.js'

// Module-level state for chart data (populated during render, used by initAnalyticsCharts)
let _chartData = null

// Keyword trend state
let _keywordCharts = { convBudget: null, benefAmount: null }
let _keywordQuery = null

/**
 * Get the current analytics page URL (reads live from address bar so it
 * always reflects the latest tab / keyword state after replaceState calls).
 * @returns {string}
 */
function currentReturnTo() {
  return window.location.pathname + window.location.search
}

/**
 * Build a URL with returnTo pointing back to the current analytics page.
 * Reads the URL dynamically so chart onClick handlers always capture the
 * latest tab/keyword state.
 * @param {string} url - Target URL (must already contain ?)
 * @returns {string} URL with returnTo appended
 */
function appendReturnTo(url) {
  return `${url}&returnTo=${encodeURIComponent(currentReturnTo())}`
}

/**
 * Render the analytics dashboard page.
 * @param {Object} params - Query parameters
 * @returns {Promise<string>} HTML
 */
export async function renderAnalyticsPage(params = {}) {
  try {
    // Fetch all data in parallel
    const [summary, byYear, byTheme, byRegion, topOrgans, status] =
      await Promise.all([
        fetchAnalyticsSummary(),
        fetchAnalyticsByYear(),
        fetchAnalyticsByTheme(),
        fetchAnalyticsByRegion(),
        fetchAnalyticsTopOrgans(),
        fetchAnalyticsStatus(),
      ])

    // Store data for chart initialization
    _chartData = { summary, byYear, byTheme, byRegion, topOrgans, status }

    const activeTab = params.tab || 'general'
    const generalHidden = activeTab === 'explorar' ? 'hidden' : ''
    const explorarHidden = activeTab === 'explorar' ? '' : 'hidden'

    return `
      <div class="max-w-5xl mx-auto">
        <div class="mb-8">
          <h1 class="text-2xl font-bold text-gray-900 mb-1">Estadísticas</h1>
          <p class="text-sm text-gray-500">
            Analisis de ${formatNumber(summary.total)} convocatorias publicadas en la BDNS
          </p>
        </div>

        <!-- Tabs -->
        <div class="flex border-b border-gray-200 mb-8" id="analytics-tabs">
          <button class="px-4 py-2.5 text-sm font-medium border-b-2 transition-colors
                         ${activeTab === 'general' ? 'border-primary text-primary' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
                  data-tab="general">
            Vista general
          </button>
          <button class="px-4 py-2.5 text-sm font-medium border-b-2 transition-colors
                         ${activeTab === 'explorar' ? 'border-primary text-primary' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
                  data-tab="explorar">
            Explorar por tema
          </button>
        </div>

        <!-- Tab: Vista general -->
        <div id="tab-general" class="${generalHidden}">
          ${createSummaryCards(summary)}

          <div class="space-y-6 mt-8">
            <!-- By year -->
            <div class="bg-white rounded-xl border border-gray-100 p-6">
              <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
                Ayudas publicadas por año
              </h2>
              <div class="h-72">
                <canvas id="chart-by-year"></canvas>
              </div>
            </div>

            <!-- Budget by year (with tax revenue comparison) -->
            <div class="bg-white rounded-xl border border-gray-100 p-6">
              <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
                Presupuesto de ayudas vs recaudacion fiscal
              </h2>
              <div class="h-80">
                <canvas id="chart-budget-by-year"></canvas>
              </div>
              <p class="text-xs text-gray-400 mt-3">
                Fuente recaudacion:
                <a href="https://sede.agenciatributaria.gob.es/Sede/datosabiertos/catalogo/hacienda/Informes_anuales_de_Recaudacion_Tributaria.shtml"
                   target="_blank" rel="noopener noreferrer"
                   class="text-primary hover:underline">
                  Agencia Tributaria — Informes Anuales de Recaudacion Tributaria
                </a>
              </p>
            </div>

            <!-- Count by theme + region side by side -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div class="bg-white rounded-xl border border-gray-100 p-6">
                <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
                  Numero de ayudas por tematica
                </h2>
                <div class="h-80">
                  <canvas id="chart-by-theme"></canvas>
                </div>
              </div>

              <div class="bg-white rounded-xl border border-gray-100 p-6">
                <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
                  Numero de ayudas por region
                </h2>
                <div class="h-80">
                  <canvas id="chart-by-region"></canvas>
                </div>
              </div>
            </div>

            <!-- Budget by theme + region side by side -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div class="bg-white rounded-xl border border-gray-100 p-6">
                <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
                  Presupuesto total por tematica
                </h2>
                <div class="h-80">
                  <canvas id="chart-budget-by-theme"></canvas>
                </div>
              </div>

              <div class="bg-white rounded-xl border border-gray-100 p-6">
                <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
                  Presupuesto total por region
                </h2>
                <div class="h-80">
                  <canvas id="chart-budget-by-region"></canvas>
                </div>
              </div>
            </div>

            <!-- Top organs table -->
            <div class="bg-white rounded-xl border border-gray-100 p-6">
              <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
                Top 10 organismos convocantes
              </h2>
              ${createTopOrgansTable(topOrgans, currentReturnTo())}
            </div>

            <!-- Status donut -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div class="bg-white rounded-xl border border-gray-100 p-6">
                <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
                  Estado actual
                </h2>
                <div class="h-64 flex items-center justify-center">
                  <canvas id="chart-status"></canvas>
                </div>
              </div>
              <div class="bg-white rounded-xl border border-gray-100 p-6 flex items-center">
                <div class="text-sm text-gray-500 space-y-3">
                  <p>
                    Los datos de esta pagina provienen de nuestra replica local de la
                    <a href="https://www.infosubvenciones.es" target="_blank" rel="noopener noreferrer"
                       class="text-primary hover:underline">Base de Datos Nacional de Subvenciones</a>
                    (BDNS), que se sincroniza diariamente.
                  </p>
                  <p>
                    Haz click en cualquier barra o segmento del grafico para ver las convocatorias concretas.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab: Explorar por tema -->
        <div id="tab-explorar" class="${explorarHidden}">
          <div class="bg-white rounded-xl border border-gray-100 p-6 mb-6">
            <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-3">
              Busca un tema para ver su evolucion
            </h2>
            <form id="keyword-trend-form" class="flex gap-3">
              <input type="text" id="keyword-trend-input"
                     class="flex-1 px-4 py-2.5 border border-gray-200 rounded-lg text-sm
                            focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                     placeholder="Ej: energias renovables, lgtbi, agricultura..."
                     value="${params.keyword ? params.keyword.replace(/"/g, '&quot;') : ''}" />
              <button type="submit"
                      class="px-5 py-2.5 bg-primary text-white text-sm font-medium rounded-lg
                             hover:bg-primary/90 transition-colors">
                Buscar
              </button>
            </form>
            <p class="text-xs text-gray-400 mt-2">
              Busca por tema, palabra clave o nombre de beneficiario para ver la evolucion en ayudas.
            </p>
          </div>
          <div id="keyword-trend-results"></div>
        </div>
      </div>
    `
  } catch (e) {
    _chartData = null
    return `
      <div class="max-w-5xl mx-auto">
        <h1 class="text-2xl font-bold text-gray-900 mb-4">Estadísticas</h1>
        <div class="bg-white rounded-xl border border-gray-100 p-8 text-center">
          <p class="text-gray-500">No se pudieron cargar los datos de analitica.</p>
          <p class="text-sm text-gray-400 mt-2">Es posible que la base de datos local aun no este disponible.</p>
        </div>
      </div>
    `
  }
}

/**
 * Create summary statistic cards.
 * @param {Object} summary
 * @returns {string} HTML
 */
function createSummaryCards(summary) {
  const cards = [
    { value: formatNumber(summary.total), label: 'Total convocatorias' },
    { value: formatCurrency(summary.total_budget), label: 'Presupuesto total' },
    { value: formatNumber(summary.open_count), label: 'Abiertas ahora' },
    { value: formatCurrency(summary.avg_budget), label: 'Presupuesto medio' },
  ]

  return `
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      ${cards.map(({ value, label }) => `
        <div class="bg-white rounded-xl border border-gray-100 p-4 text-center">
          <div class="text-xl font-bold text-gray-900">${value}</div>
          <div class="text-xs text-gray-500 mt-1">${label}</div>
        </div>
      `).join('')}
    </div>
  `
}

/**
 * Create top organs ranking table.
 * @param {Array} organs
 * @param {string} returnTo - URL to return to from search results
 * @returns {string} HTML
 */
function createTopOrgansTable(organs, returnTo) {
  if (!organs || organs.length === 0) {
    return '<p class="text-sm text-gray-400">Sin datos</p>'
  }
  return `
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-100">
            <th class="text-left py-2 text-xs font-medium text-gray-500 uppercase">#</th>
            <th class="text-left py-2 text-xs font-medium text-gray-500 uppercase">Organismo</th>
            <th class="text-right py-2 text-xs font-medium text-gray-500 uppercase">Convocatorias</th>
            <th class="text-right py-2 text-xs font-medium text-gray-500 uppercase">Presupuesto</th>
          </tr>
        </thead>
        <tbody>
          ${organs.map((org, i) => {
            const orgUrl = `/buscar?q=${encodeURIComponent(org.label)}&returnTo=${encodeURIComponent(returnTo)}`
            return `
            <tr class="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                data-link="${orgUrl}">
              <td class="py-2.5 text-gray-400">${i + 1}</td>
              <td class="py-2.5">
                <div class="font-medium text-gray-900">${org.label}</div>
                ${org.sublabel ? `<div class="text-xs text-gray-400">${org.sublabel}</div>` : ''}
              </td>
              <td class="py-2.5 text-right text-gray-700">${formatNumber(org.count)}</td>
              <td class="py-2.5 text-right text-gray-700">${formatCurrency(org.budget)}</td>
            </tr>
          `}).join('')}
        </tbody>
      </table>
    </div>
  `
}

/**
 * Initialize Chart.js charts after DOM render.
 * Called from main.js after render().
 */
export function initAnalyticsCharts() {
  if (!_chartData || typeof Chart === 'undefined') return

  const { byYear, byTheme, byRegion, status } = _chartData

  const primaryColor = '#4f46e5'

  // By year — bar chart
  const yearCtx = document.getElementById('chart-by-year')
  if (yearCtx && byYear.length > 0) {
    new Chart(yearCtx, {
      type: 'bar',
      data: {
        labels: byYear.map(d => d.label),
        datasets: [{
          label: 'Convocatorias',
          data: byYear.map(d => d.count),
          backgroundColor: primaryColor,
          borderRadius: 4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: { callback: v => formatNumber(v) } },
        },
        onClick: (_, elements) => {
          if (elements.length > 0) {
            const idx = elements[0].index
            const year = byYear[idx].label
            navigate(appendReturnTo(`/buscar?yearFrom=${year}&yearTo=${year}`))
          }
        },
      },
    })
  }

  // Budget by year — dual bar chart (grants budget + tax revenue)
  const budgetYearCtx = document.getElementById('chart-budget-by-year')
  if (budgetYearCtx && byYear.length > 0) {
    const hasTaxData = byYear.some(d => d.tax_revenue)
    const datasets = [{
      label: 'Presupuesto ayudas',
      data: byYear.map(d => d.budget),
      backgroundColor: '#10b981',
      borderRadius: 4,
    }]
    if (hasTaxData) {
      datasets.push({
        label: 'Recaudacion fiscal',
        data: byYear.map(d => d.tax_revenue),
        backgroundColor: '#3b82f6',
        borderRadius: 4,
      })
    }

    new Chart(budgetYearCtx, {
      type: 'bar',
      data: {
        labels: byYear.map(d => d.label),
        datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: hasTaxData },
          tooltip: {
            callbacks: {
              label: ctx => `${ctx.dataset.label}: ${formatCurrency(ctx.raw)}`,
            },
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { callback: v => formatCurrency(v) },
          },
        },
        onClick: (_, elements) => {
          if (elements.length > 0) {
            const idx = elements[0].index
            const year = byYear[idx].label
            navigate(appendReturnTo(`/buscar?yearFrom=${year}&yearTo=${year}`))
          }
        },
      },
    })
  }

  // By theme — horizontal bar (count)
  const themeCtx = document.getElementById('chart-by-theme')
  if (themeCtx && byTheme.length > 0) {
    new Chart(themeCtx, {
      type: 'bar',
      data: {
        labels: byTheme.map(d => truncateLabel(d.label, 30)),
        datasets: [{
          label: 'Convocatorias',
          data: byTheme.map(d => d.count),
          backgroundColor: primaryColor,
          borderRadius: 4,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true },
          y: { ticks: { font: { size: 11 } } },
        },
        onClick: (_, elements) => {
          if (elements.length > 0) {
            const idx = elements[0].index
            const theme = byTheme[idx]
            navigate(appendReturnTo(`/buscar?descripcionFinalidad=${encodeURIComponent(theme.label)}`))
          }
        },
      },
    })
  }

  // By region — horizontal bar
  const regionCtx = document.getElementById('chart-by-region')
  if (regionCtx && byRegion.length > 0) {
    new Chart(regionCtx, {
      type: 'bar',
      data: {
        labels: byRegion.map(d => truncateLabel(d.label, 25)),
        datasets: [{
          label: 'Convocatorias',
          data: byRegion.map(d => d.count),
          backgroundColor: '#10b981',
          borderRadius: 4,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true },
          y: { ticks: { font: { size: 11 } } },
        },
        onClick: (_, elements) => {
          if (elements.length > 0) {
            const idx = elements[0].index
            const region = byRegion[idx]
            navigate(appendReturnTo(`/buscar?regionDesc=${encodeURIComponent(region.label)}`))
          }
        },
      },
    })
  }

  // Budget by theme — horizontal bar
  const budgetThemeCtx = document.getElementById('chart-budget-by-theme')
  if (budgetThemeCtx && byTheme.length > 0) {
    new Chart(budgetThemeCtx, {
      type: 'bar',
      data: {
        labels: byTheme.map(d => truncateLabel(d.label, 30)),
        datasets: [{
          label: 'Presupuesto',
          data: byTheme.map(d => d.budget),
          backgroundColor: primaryColor,
          borderRadius: 4,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true, ticks: { callback: v => formatCurrency(v) } },
          y: { ticks: { font: { size: 11 } } },
        },
        onClick: (_, elements) => {
          if (elements.length > 0) {
            const idx = elements[0].index
            const theme = byTheme[idx]
            navigate(appendReturnTo(`/buscar?descripcionFinalidad=${encodeURIComponent(theme.label)}`))
          }
        },
      },
    })
  }

  // Budget by region — horizontal bar
  const budgetRegionCtx = document.getElementById('chart-budget-by-region')
  if (budgetRegionCtx && byRegion.length > 0) {
    // Sort by budget descending for this chart
    const regionsByBudget = [...byRegion].sort((a, b) => b.budget - a.budget)
    new Chart(budgetRegionCtx, {
      type: 'bar',
      data: {
        labels: regionsByBudget.map(d => truncateLabel(d.label, 25)),
        datasets: [{
          label: 'Presupuesto',
          data: regionsByBudget.map(d => d.budget),
          backgroundColor: '#10b981',
          borderRadius: 4,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true, ticks: { callback: v => formatCurrency(v) } },
          y: { ticks: { font: { size: 11 } } },
        },
        onClick: (_, elements) => {
          if (elements.length > 0) {
            const idx = elements[0].index
            const region = regionsByBudget[idx]
            navigate(appendReturnTo(`/buscar?regionDesc=${encodeURIComponent(region.label)}`))
          }
        },
      },
    })
  }

  // Status — doughnut
  const statusCtx = document.getElementById('chart-status')
  if (statusCtx && status.total > 0) {
    new Chart(statusCtx, {
      type: 'doughnut',
      data: {
        labels: ['Abiertas', 'Cerradas'],
        datasets: [{
          data: [status.open, status.closed],
          backgroundColor: ['#10b981', '#ef4444'],
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' },
        },
        onClick: (_, elements) => {
          if (elements.length > 0) {
            const idx = elements[0].index
            const estado = idx === 0 ? 'abiertas' : 'cerradas'
            navigate(appendReturnTo(`/buscar?estado=${estado}`))
          }
        },
      },
    })
  }
}

/**
 * Initialize keyword trend tab: tabs, form, auto-search.
 * Called from main.js after render().
 */
export function initKeywordTrend() {
  const tabs = document.getElementById('analytics-tabs')
  const generalTab = document.getElementById('tab-general')
  const explorarTab = document.getElementById('tab-explorar')
  const form = document.getElementById('keyword-trend-form')
  const input = document.getElementById('keyword-trend-input')

  if (!tabs || !generalTab || !explorarTab) return

  // Tab click handlers
  tabs.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-tab]')
    if (!btn) return

    const tab = btn.dataset.tab
    switchTab(tab, generalTab, explorarTab, tabs)
  })

  // Form submit
  if (form && input) {
    form.addEventListener('submit', (e) => {
      e.preventDefault()
      const q = input.value.trim()
      if (!q) return
      history.replaceState(null, '', `/estadisticas?tab=explorar&keyword=${encodeURIComponent(q)}`)
      performKeywordTrendSearch(q)
    })
  }

  // Auto-search if keyword in URL
  if (input && input.value.trim()) {
    performKeywordTrendSearch(input.value.trim())
  }
}

/**
 * Switch between tabs.
 */
function switchTab(tab, generalEl, explorarEl, tabsEl) {
  const buttons = tabsEl.querySelectorAll('[data-tab]')
  buttons.forEach(btn => {
    const isActive = btn.dataset.tab === tab
    btn.classList.toggle('border-primary', isActive)
    btn.classList.toggle('text-primary', isActive)
    btn.classList.toggle('border-transparent', !isActive)
    btn.classList.toggle('text-gray-500', !isActive)
  })

  if (tab === 'general') {
    generalEl.classList.remove('hidden')
    explorarEl.classList.add('hidden')
    history.replaceState(null, '', '/estadisticas')
  } else {
    generalEl.classList.add('hidden')
    explorarEl.classList.remove('hidden')
    const keyword = _keywordQuery ? `&keyword=${encodeURIComponent(_keywordQuery)}` : ''
    history.replaceState(null, '', `/estadisticas?tab=explorar${keyword}`)
  }
}

/**
 * Perform keyword trend search and render results.
 */
async function performKeywordTrendSearch(q) {
  const resultsEl = document.getElementById('keyword-trend-results')
  if (!resultsEl) return

  _keywordQuery = q

  // Show loading
  resultsEl.innerHTML = `
    <div class="flex items-center justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      <span class="ml-3 text-sm text-gray-500">Buscando "${q}"...</span>
    </div>
  `

  try {
    // Fetch trend data and grants in parallel
    const [trendData, grantsData] = await Promise.all([
      fetchKeywordTrend(q),
      semanticSearch({ q, topK: 20 }),
    ])

    const { total_matches, by_year, beneficiarios } = trendData
    const grants = grantsData.content || []
    const hasBeneficiarios = beneficiarios && beneficiarios.total_matches > 0
    const hasConvocatorias = total_matches > 0

    if (!hasConvocatorias && !hasBeneficiarios) {
      resultsEl.innerHTML = `
        <div class="bg-white rounded-xl border border-gray-100 p-8 text-center">
          <p class="text-gray-500">No se encontraron ayudas para "${q}".</p>
          <p class="text-sm text-gray-400 mt-2">Prueba con otro termino de busqueda.</p>
        </div>
      `
      return
    }

    // Snapshot returnTo now (after replaceState has updated the URL)
    const returnTo = currentReturnTo()

    // Build header text
    const parts = []
    if (hasConvocatorias) parts.push(`${formatNumber(total_matches)} ayudas`)
    if (hasBeneficiarios) parts.push(`${formatNumber(beneficiarios.total_matches)} beneficiarios`)
    const headerText = parts.join(' y ')

    // Convocatorias section (conditional)
    const grantsSection = hasConvocatorias ? `
      <div>
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-semibold text-gray-900 uppercase tracking-wide">
            Ayudas mas relevantes
          </h3>
          <a href="/buscar?q=${encodeURIComponent(q)}&returnTo=${encodeURIComponent(returnTo)}" data-link="/buscar?q=${encodeURIComponent(q)}&returnTo=${encodeURIComponent(returnTo)}"
             class="text-sm text-primary hover:underline">
            Ver todas &rarr;
          </a>
        </div>
        <div id="keyword-grants-list" class="space-y-3">
          ${grants.map(g => createGrantCard(g)).join('')}
        </div>
      </div>
    ` : ''

    // Beneficiarios section (conditional)
    const beneficiariosSection = hasBeneficiarios ? `
      <div>
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-semibold text-gray-900 uppercase tracking-wide">
            Beneficiarios mas relevantes
          </h3>
          <a href="/beneficiarios?q=${encodeURIComponent(q)}&returnTo=${encodeURIComponent(returnTo)}" data-link="/beneficiarios?q=${encodeURIComponent(q)}&returnTo=${encodeURIComponent(returnTo)}"
             class="text-sm text-primary hover:underline">
            Ver en beneficiarios &rarr;
          </a>
        </div>
        <div id="keyword-beneficiarios-list" class="bg-white rounded-xl border border-gray-100 p-4">
          ${createBeneficiaryList(beneficiarios.top_beneficiarios, 1)}
        </div>
      </div>
    ` : ''

    // Build results HTML
    resultsEl.innerHTML = `
      <p class="text-sm text-gray-600 mb-6">
        <span class="font-semibold text-gray-900">${headerText}</span> encontrados para
        "<span class="font-medium">${q}</span>"
      </p>

      <!-- Trend charts — one per data source, conditional -->
      <div class="grid grid-cols-1 ${hasConvocatorias && hasBeneficiarios ? 'lg:grid-cols-2' : ''} gap-6 mb-8">
        ${hasConvocatorias ? `
        <div class="bg-white rounded-xl border border-gray-100 p-6">
          <h3 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
            Presupuesto convocado por año
          </h3>
          <div class="h-64">
            <canvas id="chart-keyword-conv-budget"></canvas>
          </div>
        </div>
        ` : ''}
        ${hasBeneficiarios ? `
        <div class="bg-white rounded-xl border border-gray-100 p-6">
          <h3 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
            Total concesionado por año
          </h3>
          <div class="h-64">
            <canvas id="chart-keyword-benef-amount"></canvas>
          </div>
        </div>
        ` : ''}
      </div>

      <!-- Year filter label -->
      <div id="keyword-year-filter" class="hidden mb-4">
        <span class="inline-flex items-center gap-2 px-3 py-1.5 bg-primary/10 text-primary text-sm rounded-full">
          <span id="keyword-year-label"></span>
          <button id="keyword-clear-year" class="hover:text-primary/70">&times;</button>
        </span>
      </div>

      <!-- Listings side by side -->
      <div class="grid grid-cols-1 ${hasConvocatorias && hasBeneficiarios ? 'lg:grid-cols-2' : ''} gap-6">
        ${grantsSection}
        ${beneficiariosSection}
      </div>
    `

    // Initialize trend charts
    initKeywordCharts(by_year, q, grants, beneficiarios)
  } catch (e) {
    resultsEl.innerHTML = `
      <div class="bg-white rounded-xl border border-gray-100 p-8 text-center">
        <p class="text-gray-500">Error al buscar "${q}".</p>
        <p class="text-sm text-gray-400 mt-2">${e.message || 'Error desconocido'}</p>
      </div>
    `
  }
}

/**
 * Create and wire keyword trend charts (conv budget + benef amount by year).
 * @param {Array} byYear - Convocatorias by year data
 * @param {string} query - Search query
 * @param {Array} grants - Semantic search grants
 * @param {Object|null} beneficiariosData - Beneficiarios trend data or null
 */
function initKeywordCharts(byYear, query, grants, beneficiariosData) {
  if (typeof Chart === 'undefined') return

  // Destroy previous charts
  if (_keywordCharts.convBudget) _keywordCharts.convBudget.destroy()
  if (_keywordCharts.benefAmount) _keywordCharts.benefAmount.destroy()

  const hasBenef = beneficiariosData && beneficiariosData.by_year && beneficiariosData.by_year.length > 0
  const benefByYear = hasBenef ? beneficiariosData.by_year : []

  // Convocatorias budget chart (green) — uses convocatorias years only
  const convBudgetCtx = document.getElementById('chart-keyword-conv-budget')
  if (convBudgetCtx && byYear.length > 0) {
    const convYears = byYear.map(d => d.year)

    _keywordCharts.convBudget = new Chart(convBudgetCtx, {
      type: 'bar',
      data: {
        labels: convYears,
        datasets: [{
          data: byYear.map(d => d.budget),
          backgroundColor: '#10b981',
          borderRadius: 4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: { label: ctx => formatCurrency(ctx.raw) },
          },
        },
        scales: {
          y: { beginAtZero: true, ticks: { callback: v => formatCurrency(v) } },
        },
        onClick: (event, elements, chart) => {
          if (elements.length === 0) return
          const idx = elements[0].index
          const year = chart.data.labels[idx]
          filterResultsByYear(query, year, grants, beneficiariosData)
        },
      },
    })
  }

  // Beneficiarios amount chart (amber) — uses beneficiarios years only
  const benefAmountCtx = document.getElementById('chart-keyword-benef-amount')
  if (benefAmountCtx && benefByYear.length > 0) {
    const benefYears = benefByYear.map(d => d.year)

    _keywordCharts.benefAmount = new Chart(benefAmountCtx, {
      type: 'bar',
      data: {
        labels: benefYears,
        datasets: [{
          data: benefByYear.map(d => d.amount),
          backgroundColor: '#f59e0b',
          borderRadius: 4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: { label: ctx => formatCurrency(ctx.raw) },
          },
        },
        scales: {
          y: { beginAtZero: true, ticks: { callback: v => formatCurrency(v) } },
        },
        onClick: (event, elements, chart) => {
          if (elements.length === 0) return
          const idx = elements[0].index
          const year = chart.data.labels[idx]
          filterResultsByYear(query, year, grants, beneficiariosData)
        },
      },
    })
  }

  // Wire clear-year button
  const clearBtn = document.getElementById('keyword-clear-year')
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      clearYearFilter(query, grants, beneficiariosData)
    })
  }
}

/**
 * Filter grants and beneficiarios lists by clicking a year bar.
 */
async function filterResultsByYear(query, year, originalGrants, beneficiariosData) {
  const listEl = document.getElementById('keyword-grants-list')
  const benefListEl = document.getElementById('keyword-beneficiarios-list')
  const filterEl = document.getElementById('keyword-year-filter')
  const labelEl = document.getElementById('keyword-year-label')
  const linkEl = listEl?.previousElementSibling?.querySelector('a[data-link]')

  // Show year filter badge
  if (filterEl && labelEl) {
    labelEl.textContent = `Filtrando por ${year}`
    filterEl.classList.remove('hidden')
  }

  // Update "Ver todas" link for convocatorias
  if (linkEl) {
    const href = `/buscar?q=${encodeURIComponent(query)}&yearFrom=${year}&yearTo=${year}&returnTo=${encodeURIComponent(currentReturnTo())}`
    linkEl.setAttribute('href', href)
    linkEl.setAttribute('data-link', href)
  }

  // Update "Ver en beneficiarios" link with year filter
  const benefLinkEl = benefListEl?.previousElementSibling?.querySelector('a[data-link]')
  if (benefLinkEl) {
    const href = `/beneficiarios?q=${encodeURIComponent(query)}&anio=${year}&returnTo=${encodeURIComponent(currentReturnTo())}`
    benefLinkEl.setAttribute('href', href)
    benefLinkEl.setAttribute('data-link', href)
  }

  // Filter convocatorias
  if (listEl) {
    listEl.innerHTML = `
      <div class="flex items-center justify-center py-8">
        <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
      </div>
    `
    try {
      const data = await semanticSearch({ q: query, topK: 20, yearFrom: year, yearTo: year })
      const grants = data.content || []
      listEl.innerHTML = grants.length > 0
        ? grants.map(g => createGrantCard(g)).join('')
        : '<p class="text-sm text-gray-400 py-4">No hay ayudas para este año.</p>'
    } catch {
      listEl.innerHTML = '<p class="text-sm text-gray-400 py-4">Error al filtrar.</p>'
    }
  }

  // Filter beneficiarios
  if (benefListEl && beneficiariosData) {
    benefListEl.innerHTML = `
      <div class="flex items-center justify-center py-8">
        <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
      </div>
    `
    try {
      const data = await searchTopBeneficiaries({ q: query, anio: year, pageSize: 20 })
      const items = data.content || []
      benefListEl.innerHTML = items.length > 0
        ? createBeneficiaryList(items, 1)
        : '<p class="text-sm text-gray-400 py-4">No hay beneficiarios para este año.</p>'
    } catch {
      benefListEl.innerHTML = '<p class="text-sm text-gray-400 py-4">Error al filtrar.</p>'
    }
  }
}

/**
 * Clear year filter and restore original grants and beneficiarios.
 */
function clearYearFilter(query, originalGrants, beneficiariosData) {
  const listEl = document.getElementById('keyword-grants-list')
  const benefListEl = document.getElementById('keyword-beneficiarios-list')
  const filterEl = document.getElementById('keyword-year-filter')
  const linkEl = listEl?.previousElementSibling?.querySelector('a[data-link]')

  if (filterEl) filterEl.classList.add('hidden')

  if (linkEl) {
    const href = `/buscar?q=${encodeURIComponent(query)}&returnTo=${encodeURIComponent(currentReturnTo())}`
    linkEl.setAttribute('href', href)
    linkEl.setAttribute('data-link', href)
  }

  // Reset "Ver en beneficiarios" link (remove year filter)
  const benefLinkEl = benefListEl?.previousElementSibling?.querySelector('a[data-link]')
  if (benefLinkEl) {
    const href = `/beneficiarios?q=${encodeURIComponent(query)}&returnTo=${encodeURIComponent(currentReturnTo())}`
    benefLinkEl.setAttribute('href', href)
    benefLinkEl.setAttribute('data-link', href)
  }

  if (listEl && originalGrants) {
    listEl.innerHTML = originalGrants.map(g => createGrantCard(g)).join('')
  }

  if (benefListEl && beneficiariosData && beneficiariosData.top_beneficiarios) {
    benefListEl.innerHTML = createBeneficiaryList(beneficiariosData.top_beneficiarios, 1)
  }
}

/**
 * Truncate a label to a max length.
 * @param {string} text
 * @param {number} max
 * @returns {string}
 */
function truncateLabel(text, max) {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}
