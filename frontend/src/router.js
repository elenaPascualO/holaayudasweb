/**
 * Simple History API router for SPA navigation.
 *
 * Routes:
 *   /                    -> Homepage (search + latest grants)
 *   /buscar              -> Search results
 *   /ayuda/:bdnsCode     -> Grant detail (deep link from HolaDatos)
 */

const routes = []
let currentHandler = null
let notFoundHandler = null

/**
 * Register a route with a pattern and handler.
 * @param {string} pattern - URL pattern (e.g., "/ayuda/:bdnsCode")
 * @param {Function} handler - Async function(params) to render the page
 */
export function registerRoute(pattern, handler) {
  // Convert pattern to regex, extracting named params
  const paramNames = []
  const regexStr = pattern.replace(/:(\w+)/g, (_, name) => {
    paramNames.push(name)
    return '([^/]+)'
  })
  const regex = new RegExp(`^${regexStr}$`)
  routes.push({ pattern, regex, paramNames, handler })
}

/**
 * Register a handler for unmatched routes (404).
 * @param {Function} handler - Function(pathname) to render the 404 page
 */
export function registerNotFound(handler) {
  notFoundHandler = handler
}

/**
 * Match a path against registered routes.
 * @param {string} path - URL path
 * @returns {{ handler: Function, params: Object } | null}
 */
function matchRoute(path) {
  // Strip trailing slash (except root)
  const cleanPath = path === '/' ? '/' : path.replace(/\/$/, '')

  for (const route of routes) {
    const match = cleanPath.match(route.regex)
    if (match) {
      const params = {}
      route.paramNames.forEach((name, i) => {
        params[name] = decodeURIComponent(match[i + 1])
      })
      return { handler: route.handler, params }
    }
  }
  return null
}

/**
 * Navigate to a path, pushing to history and rendering.
 * @param {string} path - URL path (may include query string)
 */
export function navigate(path) {
  // Parse query params
  const [pathname, queryString] = path.split('?')
  const queryParams = queryString ? Object.fromEntries(new URLSearchParams(queryString)) : {}

  window.history.pushState({}, '', path)
  handleRoute(pathname, queryParams)
}

/**
 * Handle the current route: match and call handler.
 * @param {string} pathname - URL path without query string
 * @param {Object} queryParams - Parsed query parameters
 */
function handleRoute(pathname, queryParams = {}) {
  const match = matchRoute(pathname)
  if (match) {
    const params = { ...match.params, ...queryParams }
    currentHandler = match.handler
    match.handler(params)
  } else if (notFoundHandler) {
    currentHandler = notFoundHandler
    notFoundHandler(pathname)
  } else {
    navigate('/')
  }
}

/**
 * Get current route parameters from the URL.
 * @returns {Object} Query parameters
 */
export function getCurrentParams() {
  return Object.fromEntries(new URLSearchParams(window.location.search))
}

/**
 * Initialize the router: handle initial route and listen for popstate.
 */
export function initRouter() {
  // Handle browser back/forward
  window.addEventListener('popstate', () => {
    const [pathname, queryString] = window.location.pathname.split('?')
    const queryParams = queryString
      ? Object.fromEntries(new URLSearchParams(queryString))
      : Object.fromEntries(new URLSearchParams(window.location.search))
    handleRoute(pathname, queryParams)
  })

  // Handle initial route
  const queryParams = Object.fromEntries(new URLSearchParams(window.location.search))
  handleRoute(window.location.pathname, queryParams)
}
