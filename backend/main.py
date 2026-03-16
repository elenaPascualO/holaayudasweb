"""Hola Ayudas API - Proxy for BDNS grants API."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

try:
    # Production: running from root with 'backend.main:app'
    from backend.config import CORS_ORIGINS
    from backend.routes import admin_router, analytics_router, beneficiarios_router, catalogs_router, concesiones_router, convocatorias_router, feedback_router, semantic_router, seo_router
    from backend.routes.admin import cancel_sync_task
    from backend.services.bdns_client import close_client
    from backend.services.beneficiarios_db import init_db
    from backend.services.convocatorias_db import init_convocatorias_db
    from backend.services.seo import get_index_html_with_meta, load_index_template
except ImportError:
    # Development: running from backend/ with 'main:app'
    from config import CORS_ORIGINS
    from routes import admin_router, analytics_router, beneficiarios_router, catalogs_router, concesiones_router, convocatorias_router, feedback_router, semantic_router, seo_router
    from routes.admin import cancel_sync_task
    from services.bdns_client import close_client
    from services.beneficiarios_db import init_db
    from services.convocatorias_db import init_convocatorias_db
    from services.seo import get_index_html_with_meta, load_index_template

# Path to built frontend (used by lifespan and static file serving)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    init_db()
    init_convocatorias_db()
    load_index_template(frontend_dist)
    yield
    cancel_sync_task()
    await close_client()


app = FastAPI(
    title="Hola Ayudas API",
    description="Proxy API for Spanish BDNS grants database",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

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
app.include_router(seo_router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "holaayudas-api"}


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
        html = get_index_html_with_meta(filename)
        if html:
            return HTMLResponse(html)

        return FileResponse(frontend_dist / "index.html")
