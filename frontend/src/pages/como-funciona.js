/**
 * "How it works" page — explains the three main features + FAQ.
 */

/**
 * Render the como-funciona page.
 * @returns {string} HTML
 */
export function renderComoFuncionaPage() {
  return `
    <div class="max-w-2xl mx-auto">
      <h1 class="text-2xl font-bold text-gray-900 mb-2">Como funciona Hola Ayudas</h1>
      <p class="text-sm text-gray-500 mb-8">
        Hola Ayudas te permite explorar las ayudas y subvenciones publicas de España de forma
        sencilla. Los datos provienen de la
        <a href="https://www.infosubvenciones.es" target="_blank" rel="noopener noreferrer"
           class="text-primary hover:underline">Base de Datos Nacional de Subvenciones (BDNS)</a>,
        que se sincroniza diariamente con nuestra base de datos local.
      </p>

      <!-- Feature 1: Search -->
      <div class="bg-white rounded-xl border border-gray-100 p-6 mb-6">
        <div class="flex items-center gap-3 mb-3">
          <div class="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
            <svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
          </div>
          <h2 class="text-lg font-semibold text-gray-900">Busqueda de ayudas</h2>
        </div>
        <p class="text-sm text-gray-600 mb-3">
          Busca convocatorias de subvenciones publicas usando lenguaje natural. Escribe lo que
          necesitas en tus propias palabras, por ejemplo
          <em class="text-gray-700">"ayudas vivienda jovenes"</em> o
          <em class="text-gray-700">"becas investigacion universitaria"</em>,
          y nuestro buscador inteligente encontrara las convocatorias mas relevantes.
        </p>
        <p class="text-sm text-gray-600 mb-4">
          En la pagina de inicio encontraras ejemplos de busquedas populares para inspirarte.
          Una vez tengas resultados, puedes refinarlos por <strong>año</strong> y
          <strong>estado</strong> (abiertas o cerradas).
        </p>
        <a href="/" data-link
           class="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline no-underline">
          Ir al buscador
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </a>
      </div>

      <!-- Feature 2: Beneficiaries -->
      <div class="bg-white rounded-xl border border-gray-100 p-6 mb-6">
        <div class="flex items-center gap-3 mb-3">
          <div class="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
            <svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
            </svg>
          </div>
          <h2 class="text-lg font-semibold text-gray-900">Beneficiarios</h2>
        </div>
        <p class="text-sm text-gray-600 mb-3">
          Consulta el ranking de los mayores receptores de subvenciones publicas en España.
          Esta seccion promueve la transparencia, permitiendote ver que entidades reciben
          mas fondos publicos cada año.
        </p>
        <p class="text-sm text-gray-600 mb-4">
          Puedes filtrar por año, buscar por nombre o NIF, y hacer clic en cada beneficiario
          para ver el detalle de las concesiones individuales que ha recibido.
        </p>
        <a href="/beneficiarios" data-link
           class="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline no-underline">
          Ver beneficiarios
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </a>
      </div>

      <!-- Feature 3: Analytics -->
      <div class="bg-white rounded-xl border border-gray-100 p-6 mb-6">
        <div class="flex items-center gap-3 mb-3">
          <div class="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
            <svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
            </svg>
          </div>
          <h2 class="text-lg font-semibold text-gray-900">Estadisticas</h2>
        </div>
        <p class="text-sm text-gray-600 mb-3">
          Explora los datos de subvenciones publicas a traves de graficos interactivos.
          Visualiza tendencias por año, distribucion por tematicas, regiones y organismos
          convocantes.
        </p>
        <p class="text-sm text-gray-600 mb-4">
          Haz clic en cualquier segmento de los graficos para navegar directamente a las
          convocatorias correspondientes.
        </p>
        <a href="/estadisticas" data-link
           class="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline no-underline">
          Ver estadisticas
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </a>
      </div>

      <!-- FAQ -->
      <div class="bg-white rounded-xl border border-gray-100 p-6 mb-6">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Preguntas frecuentes</h2>

        <details class="group border-b border-gray-100 last:border-b-0">
          <summary class="flex items-center justify-between py-3 cursor-pointer text-sm font-medium text-gray-900 hover:text-primary transition-colors">
            ¿Que es la BDNS?
            <svg class="w-4 h-4 text-gray-400 group-open:rotate-180 transition-transform shrink-0 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </summary>
          <div class="pb-4 text-sm text-gray-600">
            La Base de Datos Nacional de Subvenciones (BDNS) es el registro oficial donde se
            publican todas las convocatorias de ayudas y subvenciones publicas en España.
            Es gestionada por el Ministerio de Hacienda y de acceso publico. Hola Ayudas
            facilita la consulta de estos datos con una interfaz moderna y busqueda inteligente.
          </div>
        </details>

        <details class="group border-b border-gray-100 last:border-b-0">
          <summary class="flex items-center justify-between py-3 cursor-pointer text-sm font-medium text-gray-900 hover:text-primary transition-colors">
            ¿De donde vienen los datos?
            <svg class="w-4 h-4 text-gray-400 group-open:rotate-180 transition-transform shrink-0 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </summary>
          <div class="pb-4 text-sm text-gray-600">
            Todos los datos provienen de la API publica de la BDNS
            (<a href="https://www.infosubvenciones.es" target="_blank" rel="noopener noreferrer"
                class="text-primary hover:underline">infosubvenciones.es</a>).
            Nuestra base de datos se sincroniza diariamente para ofrecer busqueda inteligente
            y estadisticas que la web oficial no proporciona.
          </div>
        </details>

        <details class="group border-b border-gray-100 last:border-b-0">
          <summary class="flex items-center justify-between py-3 cursor-pointer text-sm font-medium text-gray-900 hover:text-primary transition-colors">
            ¿Los datos son en tiempo real?
            <svg class="w-4 h-4 text-gray-400 group-open:rotate-180 transition-transform shrink-0 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </summary>
          <div class="pb-4 text-sm text-gray-600">
            No, los datos no se consultan en tiempo real. La base de datos de Hola Ayudas se
            sincroniza diariamente con la BDNS. Esto significa que puede haber un desfase de
            hasta 24 horas respecto a la publicacion oficial. A cambio, ofrecemos busqueda
            inteligente y estadisticas que no estan disponibles en la web oficial.
          </div>
        </details>

        <details class="group border-b border-gray-100 last:border-b-0">
          <summary class="flex items-center justify-between py-3 cursor-pointer text-sm font-medium text-gray-900 hover:text-primary transition-colors">
            ¿Es gratis?
            <svg class="w-4 h-4 text-gray-400 group-open:rotate-180 transition-transform shrink-0 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </summary>
          <div class="pb-4 text-sm text-gray-600">
            Si, Hola Ayudas es completamente gratuito. Es un proyecto de
            <a href="/contacto" data-link class="text-primary hover:underline no-underline">HolaDatos</a>,
            una iniciativa para hacer los datos publicos mas accesibles y comprensibles
            para la ciudadania.
          </div>
        </details>

        <details class="group border-b border-gray-100 last:border-b-0">
          <summary class="flex items-center justify-between py-3 cursor-pointer text-sm font-medium text-gray-900 hover:text-primary transition-colors">
            ¿Como funciona la busqueda inteligente?
            <svg class="w-4 h-4 text-gray-400 group-open:rotate-180 transition-transform shrink-0 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </summary>
          <div class="pb-4 text-sm text-gray-600">
            Utilizamos inteligencia artificial para entender el significado de tu busqueda,
            no solo las palabras exactas. Por ejemplo, si buscas "ayudas para montar un negocio",
            encontrara convocatorias sobre emprendimiento, creacion de empresas y autoempleo,
            aunque no contengan esas palabras exactas.
          </div>
        </details>

        <details class="group border-b border-gray-100 last:border-b-0">
          <summary class="flex items-center justify-between py-3 cursor-pointer text-sm font-medium text-gray-900 hover:text-primary transition-colors">
            ¿Puedo sugerir mejoras?
            <svg class="w-4 h-4 text-gray-400 group-open:rotate-180 transition-transform shrink-0 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </summary>
          <div class="pb-4 text-sm text-gray-600">
            ¡Por supuesto! Nos encanta recibir sugerencias. Puedes escribirnos desde la pagina de
            <a href="/contacto" data-link class="text-primary hover:underline no-underline">contacto</a>
            con cualquier idea, problema o mejora que se te ocurra.
          </div>
        </details>
      </div>
    </div>
  `
}
