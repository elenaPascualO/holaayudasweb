"""Sync beneficiarios data from BDNS API into local SQLite.

Usage:
    uv run python -m backend.scripts.sync_beneficiarios

Downloads all top beneficiaries from the BDNS API for every available year,
then replaces the local SQLite database in a single transaction.
"""

import asyncio
import logging
import sqlite3
import time
from datetime import datetime, timezone

import httpx

from backend.config import BDNS_BASE_URL, BENEFICIARIOS_DB_PATH
from backend.services.beneficiarios_db import init_db, sync_beneficiarios

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Concurrency limit for BDNS requests
MAX_CONCURRENT = 3
PAGE_SIZE = 50
REQUEST_TIMEOUT = 30.0


async def fetch_years(client: httpx.AsyncClient) -> list[int]:
    """Fetch available years from BDNS API.

    Returns:
        Sorted list of years (descending).
    """
    response = await client.get("/grandesbeneficiarios/anios")
    response.raise_for_status()
    data = response.json()

    # API returns [{id: 2024, descripcion: 2024}, ...] or plain ints
    years = []
    for item in data:
        if isinstance(item, dict):
            years.append(int(item.get("id", item.get("descripcion", 0))))
        else:
            years.append(int(item))

    return sorted(years, reverse=True)


async def fetch_page(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    year: int,
    page: int,
) -> list[dict]:
    """Fetch a single page of beneficiarios for a year.

    Args:
        client: httpx client.
        semaphore: Concurrency limiter.
        year: Year filter.
        page: Page number (0-indexed).

    Returns:
        List of beneficiary records from the page.
    """
    async with semaphore:
        params = {
            "anios": [year],
            "page": page,
            "pageSize": PAGE_SIZE,
            "order": "ayudaETotal",
            "direccion": "desc",
        }
        response = await client.get(
            "/grandesbeneficiarios/busqueda", params=params
        )
        response.raise_for_status()
        data = response.json()
        return data.get("content", [])


async def fetch_all_for_year(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    year: int,
) -> list[dict]:
    """Fetch all beneficiarios for a given year.

    Fetches the first page to determine total pages, then fetches
    remaining pages in parallel.

    Args:
        client: httpx client.
        semaphore: Concurrency limiter.
        year: Year to fetch.

    Returns:
        All beneficiary records for the year.
    """
    # First page to get total
    async with semaphore:
        params = {
            "anios": [year],
            "page": 0,
            "pageSize": PAGE_SIZE,
            "order": "ayudaETotal",
            "direccion": "desc",
        }
        response = await client.get(
            "/grandesbeneficiarios/busqueda", params=params
        )
        response.raise_for_status()
        first_data = response.json()

    records = first_data.get("content", [])
    total_pages = first_data.get("totalPages", 1)
    total_elements = first_data.get("totalElements", 0)
    logger.info("Year %d: %d records across %d pages", year, total_elements, total_pages)

    if total_pages <= 1:
        return records

    # Fetch remaining pages in parallel
    tasks = [
        fetch_page(client, semaphore, year, page)
        for page in range(1, total_pages)
    ]
    pages = await asyncio.gather(*tasks)
    for page_records in pages:
        records.extend(page_records)

    return records


async def run_sync() -> None:
    """Main sync entrypoint: fetch all data and write to SQLite."""
    start = time.monotonic()
    logger.info("Starting beneficiarios sync...")

    # Ensure DB schema exists
    init_db()

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with httpx.AsyncClient(
        base_url=BDNS_BASE_URL,
        timeout=REQUEST_TIMEOUT,
        headers={"Accept": "application/json"},
    ) as client:
        # Get available years
        years = await fetch_years(client)
        logger.info("Available years: %s", years)

        # Fetch all records for all years
        all_records: list[dict] = []
        for year in years:
            year_records = await fetch_all_for_year(client, semaphore, year)
            all_records.extend(year_records)

    logger.info("Total records fetched: %d", len(all_records))

    # Write to SQLite
    count = sync_beneficiarios(all_records)

    # Update sync metadata
    conn = sqlite3.connect(BENEFICIARIOS_DB_PATH)
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO sync_metadata (key, value) VALUES ('last_sync', ?)",
            (now,),
        )
        conn.commit()
    finally:
        conn.close()

    elapsed = time.monotonic() - start
    logger.info("Sync complete: %d records in %.1fs", count, elapsed)


def main() -> None:
    """CLI entrypoint."""
    asyncio.run(run_sync())


if __name__ == "__main__":
    main()
