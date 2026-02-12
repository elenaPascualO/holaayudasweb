"""Hola Ayudas API - Proxy for BDNS grants API."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    # Production: running from root with 'backend.main:app'
    from backend.config import CORS_ORIGINS
    from backend.routes import catalogs_router, convocatorias_router
    from backend.services.bdns_client import close_client
except ImportError:
    # Development: running from backend/ with 'main:app'
    from config import CORS_ORIGINS
    from routes import catalogs_router, convocatorias_router
    from services.bdns_client import close_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
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
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Register API routes
app.include_router(convocatorias_router)
app.include_router(catalogs_router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Health check for Railway."""
    return {"status": "ok", "service": "holaayudas-api"}


# Mount frontend static files (must be last, so API routes take priority)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
