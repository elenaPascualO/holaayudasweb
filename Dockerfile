# Hola Ayudas - Unified Dockerfile
# Multi-stage build: Frontend (Bun) + Backend (Python/FastAPI)

# Stage 1: Build frontend
FROM oven/bun:1 AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ .
RUN bun run build

# Stage 2: Python backend
FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy backend code and pyproject.toml
COPY backend/ backend/
COPY pyproject.toml .

# Install Python dependencies
RUN uv pip install --system --no-cache .

# Copy built frontend from first stage
COPY --from=frontend-builder /app/frontend/dist frontend/dist

# Create data directory for SQLite databases
RUN mkdir -p /app/data

EXPOSE 8000

# Use shell form to expand $PORT environment variable (Railway sets this)
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info
