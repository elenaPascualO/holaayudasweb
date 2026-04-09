/**
 * Top navigation header with mobile hamburger menu.
 */

export function createHeader() {
  return `
    <header class="bg-white border-b border-gray-100 sticky top-0 z-40">
      <div class="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
        <a href="/" data-link class="flex items-center gap-2 no-underline hover:opacity-70 transition-opacity">
          <div class="w-8 h-8 rounded-full flex items-center justify-center" style="background: linear-gradient(135deg, #2d2d2d, #1a1a1a);">
            <span class="font-bold text-xs" style="color: #d4cfc7; font-family: Georgia, 'Times New Roman', serif;">ha</span>
          </div>
          <span class="text-xl font-bold text-gray-900">Hola Ayudas</span>
        </a>
        <nav class="hidden sm:flex items-center gap-3" id="nav-desktop">
          <a href="/beneficiarios" data-link
             class="text-sm font-medium px-3 py-1 rounded-full bg-primary/5 text-primary hover:bg-primary/10 transition-colors no-underline">
            Beneficiarios
          </a>
          <a href="/estadisticas" data-link
             class="text-sm font-medium px-3 py-1 rounded-full bg-primary/5 text-primary hover:bg-primary/10 transition-colors no-underline">
            Estadísticas
          </a>
          <a href="/como-funciona" data-link
             class="text-sm font-medium px-3 py-1 rounded-full text-gray-500 hover:bg-gray-100 transition-colors no-underline">
            Ayuda
          </a>
          <a href="/contacto" data-link
             class="text-sm font-medium px-3 py-1 rounded-full text-gray-500 hover:bg-gray-100 transition-colors no-underline">
            Contacto
          </a>
        </nav>
        <button class="sm:hidden p-2 -mr-2 text-gray-600 hover:text-gray-900 transition-colors"
                id="mobile-menu-btn" aria-label="Abrir menu" aria-expanded="false">
          <svg class="w-6 h-6" id="menu-icon-open" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
          </svg>
          <svg class="w-6 h-6 hidden" id="menu-icon-close" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
      <nav class="hidden sm:hidden border-t border-gray-100 bg-white" id="nav-mobile">
        <div class="max-w-5xl mx-auto px-4 py-3 flex flex-col gap-2">
          <a href="/beneficiarios" data-link
             class="text-sm font-medium px-3 py-2 rounded-lg bg-primary/5 text-primary hover:bg-primary/10 transition-colors no-underline">
            Beneficiarios
          </a>
          <a href="/estadisticas" data-link
             class="text-sm font-medium px-3 py-2 rounded-lg bg-primary/5 text-primary hover:bg-primary/10 transition-colors no-underline">
            Estadísticas
          </a>
          <a href="/como-funciona" data-link
             class="text-sm font-medium px-3 py-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors no-underline">
            Ayuda
          </a>
          <a href="/contacto" data-link
             class="text-sm font-medium px-3 py-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors no-underline">
            Contacto
          </a>
        </div>
      </nav>
    </header>
  `
}

/**
 * Initialize mobile menu toggle behavior.
 * Call this after the header is rendered in the DOM.
 */
export function initMobileMenu() {
  const btn = document.getElementById('mobile-menu-btn')
  const nav = document.getElementById('nav-mobile')
  const iconOpen = document.getElementById('menu-icon-open')
  const iconClose = document.getElementById('menu-icon-close')
  if (!btn || !nav) return

  btn.addEventListener('click', () => {
    const isOpen = !nav.classList.contains('hidden')
    nav.classList.toggle('hidden', isOpen)
    iconOpen.classList.toggle('hidden', !isOpen)
    iconClose.classList.toggle('hidden', isOpen)
    btn.setAttribute('aria-expanded', String(!isOpen))
  })

  // Close menu when a link is clicked
  nav.addEventListener('click', (e) => {
    if (e.target.closest('a[data-link]')) {
      nav.classList.add('hidden')
      iconOpen.classList.remove('hidden')
      iconClose.classList.add('hidden')
      btn.setAttribute('aria-expanded', 'false')
    }
  })
}
