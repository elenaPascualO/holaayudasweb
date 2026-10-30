"""Hola Ayudas API - Proxy for BDNS grants API."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

try:
    # Production: running from root with 'backend.main:app'
    from backend.config import CORS_ORIGINS, IS_PRODUCTION, SITE_BASE_URL
    from backend.routes import admin_router, analytics_router, beneficiarios_router, catalogs_router, concesiones_router, convocatorias_router, feedback_router, posts_router, semantic_router, seo_router
    from backend.routes.admin import cancel_sync_task
    from backend.routes.posts import cancel_generate_task
    from backend.services.bdns_client import close_client
    from backend.services.beneficiarios_db import init_db
    from backend.services.convocatorias_db import init_convocatorias_db
    from backend.services.posts_db import init_posts_db
    from backend.services.seo import get_index_html_with_meta, load_index_template
except ImportError:
    # Development: running from backend/ with 'main:app'
    from config import CORS_ORIGINS, IS_PRODUCTION, SITE_BASE_URL
    from routes import admin_router, analytics_router, beneficiarios_router, catalogs_router, concesiones_router, convocatorias_router, feedback_router, posts_router, semantic_router, seo_router
    from routes.admin import cancel_sync_task
    from routes.posts import cancel_generate_task
    from services.bdns_client import close_client
    from services.beneficiarios_db import init_db
    from services.convocatorias_db import init_convocatorias_db
    from services.posts_db import init_posts_db
    from services.seo import get_index_html_with_meta, load_index_template

# Path to built frontend (used by lifespan and static file serving)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    init_db()
    init_convocatorias_db()
    init_posts_db()
    load_index_template(frontend_dist)

    # Load FAISS index in background (search works FTS-only until ready).
    # Reads the saved index from disk; only builds from SQLite if there is none.
    # Skip in test environments to avoid loading 6GB+ of embeddings
    faiss_load_task = None
    if not os.environ.get("TESTING"):
        try:
            from backend.services.faiss_index import load_or_build
        except ImportError:
            from services.faiss_index import load_or_build

        async def _load_faiss():
            try:
                await asyncio.to_thread(load_or_build)
            except Exception as e:
                logging.getLogger(__name__).error("FAISS index load failed: %s", e)

        faiss_load_task = asyncio.create_task(_load_faiss())

    # Pregenerate sitemaps in background if missing or older than 24h
    # (routes build them on demand in a thread until the files exist)
    sitemaps_task = None
    if not os.environ.get("TESTING"):
        try:
            from backend.services import sitemaps
        except ImportError:
            from services import sitemaps

        async def _generate_sitemaps():
            try:
                if await asyncio.to_thread(sitemaps.needs_regeneration):
                    await asyncio.to_thread(sitemaps.generate_all)
                else:
                    logging.getLogger(__name__).info("Sitemaps are up to date — not regenerating")
            except Exception as e:
                logging.getLogger(__name__).error("Sitemap generation failed: %s", e)

        sitemaps_task = asyncio.create_task(_generate_sitemaps())

    yield

    if sitemaps_task and not sitemaps_task.done():
        sitemaps_task.cancel()

    if faiss_load_task and not faiss_load_task.done():
        faiss_load_task.cancel()
        try:
            await faiss_load_task
        except asyncio.CancelledError:
            pass
    cancel_sync_task()
    cancel_generate_task()
    await close_client()


app = FastAPI(
    title="Hola Ayudas API",
    description="Proxy API for Spanish BDNS grants database",
    version="0.1.0",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    lifespan=lifespan,
)

logger = logging.getLogger(__name__)


# Security headers + error handling middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses and catch unhandled exceptions in production."""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            if IS_PRODUCTION:
                logger.exception(
                    "Unhandled exception on %s %s", request.method, request.url.path
                )
                response = JSONResponse(
                    status_code=500, content={"detail": "Internal server error"}
                )
            else:
                raise
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)


# WWW redirect middleware (301) — fixes canonical duplication in Google
class WwwRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect non-www requests to www in production."""

    async def dispatch(self, request: Request, call_next):
        host = request.url.hostname or ""
        if (
            IS_PRODUCTION
            and host
            and not host.startswith("www.")
            and "." in host  # skip localhost, test hosts, IP addresses without dots
        ):
            target = SITE_BASE_URL + request.url.path
            if request.url.query:
                target += f"?{request.url.query}"
            return Response(status_code=301, headers={"Location": target})
        return await call_next(request)


app.add_middleware(WwwRedirectMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# Register API routes
app.include_router(convocatorias_router)
app.include_router(catalogs_router)
app.include_router(concesiones_router)
app.include_router(beneficiarios_router)
app.include_router(feedback_router)
app.include_router(semantic_router)
app.include_router(analytics_router)
app.include_router(admin_router)
app.include_router(posts_router)
app.include_router(seo_router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "holaayudas-api"}


async def render_page_with_meta(filename: str) -> HTMLResponse | None:
    """Build index.html with SEO meta/body for a path, off the event loop.

    Grant pages (/ayuda/{code}) read the grant from SQLite, so this runs in a
    worker thread to avoid blocking other requests.

    Returns:
        HTMLResponse, or None if the path has no SEO configuration.
    """
    result = await asyncio.to_thread(get_index_html_with_meta, filename)
    if not result:
        return None
    html, status_code = result
    return HTMLResponse(html, status_code=status_code)


# Serve frontend static files and SPA fallback (must be last, so API routes take priority)
if frontend_dist.exists():
    # Mount static assets (JS, CSS, images, etc.)
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="static-assets")

    # Serve known static files at root (favicon, robots.txt, sitemap, etc.)
    @app.get("/{filename:path}", response_model=None)
    async def spa_fallback(request: Request, filename: str) -> Response:
        """Serve static files if they exist, otherwise fallback to index.html with SEO meta tags."""
        file_path = frontend_dist / filename
        if filename and file_path.is_file():
            return FileResponse(file_path)

        # Inject SEO meta tags for crawlers and social media previews
        page = await render_page_with_meta(filename)
        if page is not None:
            return page

        return FileResponse(frontend_dist / "index.html")
