/**
 * Top navigation header.
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
        <span class="text-xs text-gray-400 hidden sm:block">
          Busca ayudas y subvenciones publicas
        </span>
      </div>
    </header>
  `
}
