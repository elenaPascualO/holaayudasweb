"""Configuration settings for Hola Ayudas."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# Environment detection
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION: bool = ENVIRONMENT == "production"

# BDNS upstream API
BDNS_BASE_URL: str = os.getenv(
    "BDNS_BASE_URL",
    "https://www.infosubvenciones.es/bdnstrans/api",
)

# Cache TTLs (seconds)
CACHE_TTL_CATALOGS: int = int(os.getenv("CACHE_TTL_CATALOGS", "86400"))  # 24h
CACHE_TTL_SEARCH: int = int(os.getenv("CACHE_TTL_SEARCH", "300"))  # 5min
CACHE_TTL_DETAIL: int = int(os.getenv("CACHE_TTL_DETAIL", "3600"))  # 1h

# BDNS request timeout (seconds)
BDNS_TIMEOUT: float = float(os.getenv("BDNS_TIMEOUT", "30.0"))

# Default page size for search results
DEFAULT_PAGE_SIZE: int = 20

# Portal identifier (always GE for general)
BDNS_VPD: str = "GE"


def get_cors_origins() -> list[str]:
    """Get CORS origins based on environment.

    In production, reads from ALLOWED_ORIGINS environment variable.
    In development, allows common localhost origins.
    """
    if IS_PRODUCTION:
        origins_str = os.getenv("ALLOWED_ORIGINS", "")
        if origins_str:
            return [o.strip() for o in origins_str.split(",") if o.strip()]
        return []

    return [
        "http://localhost:5174",
        "http://localhost:8001",
        "http://127.0.0.1:5174",
    ]


CORS_ORIGINS: list[str] = get_cors_origins()

# SQLite database for beneficiarios text search
BENEFICIARIOS_DB_PATH: str = os.getenv(
    "BENEFICIARIOS_DB_PATH",
    str(Path(__file__).parent.parent / "data" / "beneficiarios.db"),
)

# SQLite database for convocatorias local replica
CONVOCATORIAS_DB_PATH: str = os.getenv(
    "CONVOCATORIAS_DB_PATH",
    str(Path(__file__).parent.parent / "data" / "convocatorias.db"),
)

# FAISS index persisted on disk (next to the convocatorias DB by default)
FAISS_INDEX_PATH: str = os.getenv(
    "FAISS_INDEX_PATH",
    str(Path(CONVOCATORIAS_DB_PATH).parent / "faiss.index"),
)

# OpenAI API key for embeddings and post generation
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# OpenAI model for social media post generation (cost-efficient)
POSTS_OPENAI_MODEL: str = os.getenv("POSTS_OPENAI_MODEL", "gpt-4o")

# Discord webhook for feedback notifications
DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

# Secret token for admin endpoints (sync cron, etc.)
ADMIN_SECRET: str = os.getenv("ADMIN_SECRET", "")

# Public base URL for sitemap and SEO canonical links
SITE_BASE_URL: str = os.getenv("SITE_BASE_URL", "https://www.holaayudas.com")

# SMTP settings for sync failure notifications
SMTP_HOST: str = os.getenv("SMTP_HOST", "")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM: str = os.getenv("SMTP_FROM", "")
ALERT_EMAIL_TO: str = os.getenv("ALERT_EMAIL_TO", "")
