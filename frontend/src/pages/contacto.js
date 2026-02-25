/**
 * Contact page — HolaDatos info + feedback form.
 */

/**
 * Render the contact page.
 * @returns {string} HTML
 */
export function renderContactoPage() {
  return `
    <div class="max-w-lg mx-auto">
      <h1 class="text-2xl font-bold text-gray-900 mb-6">Contacto</h1>

      <!-- HolaDatos info -->
      <div class="bg-white rounded-xl border border-gray-100 p-6 mb-6">
        <div class="flex items-center gap-3 mb-3">
          <div class="w-10 h-10 rounded-full flex items-center justify-center shrink-0"
               style="background: linear-gradient(135deg, #2d2d2d, #1a1a1a);">
            <span class="font-bold text-sm" style="color: #d4cfc7; font-family: Georgia, 'Times New Roman', serif;">hd</span>
          </div>
          <div>
            <p class="font-semibold text-gray-900">HolaDatos</p>
            <p class="text-xs text-gray-400">Datos publicos, accesibles para todos</p>
          </div>
        </div>
        <p class="text-sm text-gray-600 mb-4">
          Hola Ayudas es un proyecto de <strong>HolaDatos</strong>, una iniciativa para hacer
          los datos publicos mas accesibles y comprensibles para la ciudadania.
        </p>
        <div class="flex items-center gap-3">
          <a href="https://x.com/hola_datos_es" target="_blank" rel="noopener noreferrer"
             class="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary transition-colors no-underline">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
            </svg>
            @hola_datos_es
          </a>
          <a href="https://www.linkedin.com/company/hola-datos/" target="_blank" rel="noopener noreferrer"
             class="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary transition-colors no-underline">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
            </svg>
            LinkedIn
          </a>
        </div>
      </div>

      <!-- Contact form -->
      <div class="bg-white rounded-xl border border-gray-100 p-6">
        <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-1">Escribenos</h2>
        <p class="text-sm text-gray-400 mb-4">
          Sugerencias, problemas o ideas para mejorar Hola Ayudas.
        </p>
        <form id="feedback-form" class="space-y-3">
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
            rows="4"
            placeholder="Tu mensaje..."
            class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg
                   focus:outline-none focus:border-primary resize-none"
          ></textarea>
          <div class="flex items-center gap-2">
            <button
              type="submit"
              class="px-5 py-2 text-sm font-medium bg-primary text-white rounded-lg
                     hover:bg-primary-dark transition-colors"
            >
              Enviar
            </button>
            <span id="feedback-status" class="text-xs text-gray-400"></span>
          </div>
        </form>
      </div>
    </div>
  `
}
