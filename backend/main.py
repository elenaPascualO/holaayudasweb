"""Hola Ayudas API - Proxy for BDNS grants API."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

try:
    # Production: running from root with 'backend.main:app'
    from backend.config import CORS_ORIGINS
    from backend.routes import admin_router, beneficiarios_router, catalogs_router, concesiones_router, convocatorias_router, feedback_router
    from backend.services.bdns_client import close_client
    from backend.services.beneficiarios_db import init_db
except ImportError:
    # Development: running from backend/ with 'main:app'
    from config import CORS_ORIGINS
    from routes import admin_router, beneficiarios_router, catalogs_router, concesiones_router, convocatorias_router, feedback_router
    from services.bdns_client import close_client
    from services.beneficiarios_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    init_db()
    yield
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
app.include_router(admin_router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Health check for Railway."""
    return {"status": "ok", "service": "holaayudas-api"}


# Serve frontend static files and SPA fallback (must be last, so API routes take priority)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    # Mount static assets (JS, CSS, images, etc.)
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="static-assets")

    # Serve known static files at root (favicon, robots.txt, sitemap, etc.)
    @app.get("/{filename:path}")
    async def spa_fallback(request: Request, filename: str) -> FileResponse:
        """Serve static files if they exist, otherwise fallback to index.html for SPA routing."""
        file_path = frontend_dist / filename
        if filename and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")
