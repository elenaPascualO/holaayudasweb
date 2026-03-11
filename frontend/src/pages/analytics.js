/**
 * Analytics dashboard page — grant data insights with Chart.js.
 */

import {
  fetchAnalyticsSummary,
  fetchAnalyticsByYear,
  fetchAnalyticsMonthlyTrend,
  fetchAnalyticsByTheme,
  fetchAnalyticsByRegion,
  fetchAnalyticsTopOrgans,
  fetchAnalyticsStatus,
} from '../utils/api.js'
import { formatNumber, formatCurrency } from '../utils/formatters.js'
import { navigate } from '../router.js'

// Module-level state for chart data (populated during render, used by initAnalyticsCharts)
let _chartData = null

const MONTH_NAMES = [
  'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
  'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
]

/**
 * Render the analytics dashboard page.
 * @param {Object} params - Query parameters
 * @returns {Promise<string>} HTML
 */
export async function renderAnalyticsPage(params = {}) {
  const currentYear = new Date().getFullYear()

  try {
    // Fetch all data in parallel
    const [summary, byYear, monthlyTrend, byTheme, byRegion, topOrgans, status] =
      await Promise.all([
        fetchAnalyticsSummary(),
        fetchAnalyticsByYear(),
        fetchAnalyticsMonthlyTrend(currentYear),
        fetchAnalyticsByTheme(),
        fetchAnalyticsByRegion(),
        fetchAnalyticsTopOrgans(),
        fetchAnalyticsStatus(),
      ])

    // Store data for chart initialization
    _chartData = { summary, byYear, monthlyTrend, byTheme, byRegion, topOrgans, status, currentYear }

    return `
      <div class="max-w-5xl mx-auto">
        <div class="mb-8">
          <h1 class="text-2xl font-bold text-gray-900 mb-1">Estadísticas</h1>
          <p class="text-sm text-gray-500">
            Analisis de ${formatNumber(summary.total)} convocatorias publicadas en la BDNS
          </p>
        </div>

        <!-- Summary cards -->
        ${createSummaryCards(summary)}

        <!-- Charts grid -->
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

          <!-- Monthly trend -->
          <div class="bg-white rounded-xl border border-gray-100 p-6">
            <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
              Tendencia mensual ${currentYear}
            </h2>
            <div class="h-64">
              <canvas id="chart-monthly"></canvas>
            </div>
          </div>

          <!-- Theme + Region side by side -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="bg-white rounded-xl border border-gray-100 p-6">
              <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
                Por tematica
              </h2>
              <div class="h-80">
                <canvas id="chart-by-theme"></canvas>
              </div>
            </div>

            <div class="bg-white rounded-xl border border-gray-100 p-6">
              <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
                Por region
              </h2>
              <div class="h-80">
                <canvas id="chart-by-region"></canvas>
              </div>
            </div>
          </div>

          <!-- Top organs table -->
          <div class="bg-white rounded-xl border border-gray-100 p-6">
            <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
              Top 10 organismos convocantes
            </h2>
            ${createTopOrgansTable(topOrgans)}
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
 * @returns {string} HTML
 */
function createTopOrgansTable(organs) {
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
          ${organs.map((org, i) => `
            <tr class="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                data-link="/buscar?q=${encodeURIComponent(org.label)}">
              <td class="py-2.5 text-gray-400">${i + 1}</td>
              <td class="py-2.5">
                <div class="font-medium text-gray-900">${org.label}</div>
                ${org.sublabel ? `<div class="text-xs text-gray-400">${org.sublabel}</div>` : ''}
              </td>
              <td class="py-2.5 text-right text-gray-700">${formatNumber(org.count)}</td>
              <td class="py-2.5 text-right text-gray-700">${formatCurrency(org.budget)}</td>
            </tr>
          `).join('')}
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

  const { byYear, monthlyTrend, byTheme, byRegion, status, currentYear } = _chartData

  const primaryColor = '#4f46e5'
  const primaryLight = 'rgba(79, 70, 229, 0.1)'

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
            navigate(`/buscar?yearFrom=${year}&yearTo=${year}`)
          }
        },
      },
    })
  }

  // Monthly trend — line chart
  const monthCtx = document.getElementById('chart-monthly')
  if (monthCtx && monthlyTrend.length > 0) {
    new Chart(monthCtx, {
      type: 'line',
      data: {
        labels: monthlyTrend.map(d => MONTH_NAMES[parseInt(d.label, 10) - 1] || d.label),
        datasets: [{
          label: 'Convocatorias',
          data: monthlyTrend.map(d => d.count),
          borderColor: primaryColor,
          backgroundColor: primaryLight,
          fill: true,
          tension: 0.3,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true },
        },
      },
    })
  }

  // By theme — horizontal bar
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
            navigate(`/buscar?descripcionFinalidad=${encodeURIComponent(theme.label)}`)
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
            navigate(`/buscar?regionDesc=${encodeURIComponent(region.label)}`)
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
            navigate(`/buscar?estado=${estado}`)
          }
        },
      },
    })
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
