"""Sync convocatorias data from BDNS API into local SQLite.

Usage:
    uv run python -m backend.scripts.sync_convocatorias [mode]

Modes:
    daily              - Incremental sync: new list entries + detail + embeddings
    full-list          - Full historical load: paginate all ~610K convocatorias
    backfill-detail    - Fetch detail for up to 3000 convocatorias without it
    backfill-embeddings - Generate embeddings for up to 500 convocatorias
"""

import asyncio
import logging
import sqlite3
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone

import httpx

from backend.config import BDNS_BASE_URL, BDNS_VPD, CONVOCATORIAS_DB_PATH
from backend.services.convocatorias_db import (
    get_embedding_text,
    get_unfetched_detail_ids,
    get_unembedded_ids,
    init_convocatorias_db,
    rebuild_fts,
    store_embeddings,
    update_convocatoria_detail,
    upsert_convocatorias_list,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

MAX_CONCURRENT = 5
PAGE_SIZE = 50
REQUEST_TIMEOUT = 30.0
DETAIL_BATCH_SIZE = 30_000
EMBEDDING_BATCH_SIZE = 10_000
EMBEDDING_API_BATCH = 500  # texts per OpenAI API call

# Callback type: receives a dict with progress info (phase, counts, etc.)
ProgressCallback = Callable[[dict], None] | None


async def fetch_search_page(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    page: int,
) -> dict:
    """Fetch a page of convocatorias from BDNS search endpoint.

    Args:
        client: httpx client.
        semaphore: Concurrency limiter.
        page: Page number (0-indexed).

    Returns:
        Full response dict with content, totalPages, etc.
    """
    async with semaphore:
        params = {
            "vpd": BDNS_VPD,
            "page": page,
            "pageSize": PAGE_SIZE,
        }
        for attempt in range(3):
            try:
                response = await client.get("/convocatorias/busqueda", params=params)
                if response.status_code == 429:
                    delay = 2.0 * (2 ** attempt)
                    logger.warning("429 on page %d, retrying in %.1fs", page, delay)
                    await asyncio.sleep(delay)
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                if attempt < 2:
                    logger.warning("Error on page %d: %s, retrying", page, e)
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    raise
        return {"content": [], "totalPages": 0}


async def fetch_detail(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    numero: str,
) -> dict | None:
    """Fetch full detail for a single convocatoria.

    Args:
        client: httpx client.
        semaphore: Concurrency limiter.
        numero: Convocatoria number.

    Returns:
        Detail dict or None on failure.
    """
    async with semaphore:
        params = {"vpd": BDNS_VPD, "numConv": numero}
        for attempt in range(3):
            try:
                response = await client.get("/convocatorias", params=params)
                if response.status_code == 429:
                    delay = 2.0 * (2 ** attempt)
                    logger.warning("429 on detail %s, retrying in %.1fs", numero, delay)
                    await asyncio.sleep(delay)
                    continue
                if response.status_code == 404:
                    logger.warning("Detail 404 for %s", numero)
                    return None
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                if attempt < 2:
                    logger.warning("Error fetching detail %s: %s, retrying", numero, e)
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    logger.error("Failed to fetch detail %s after retries: %s", numero, e)
                    return None
        return None


async def sync_full_list(
    progress_callback: ProgressCallback = None,
) -> int:
    """Paginate all convocatorias from BDNS and insert into SQLite.

    Args:
        progress_callback: Optional callback receiving progress dicts.

    Returns:
        Total records inserted.
    """
    logger.info("Starting full-list sync...")
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    total_inserted = 0

    async with httpx.AsyncClient(
        base_url=BDNS_BASE_URL,
        timeout=REQUEST_TIMEOUT,
        headers={"Accept": "application/json"},
    ) as client:
        # Get first page to know total
        first = await fetch_search_page(client, semaphore, 0)
        total_pages = first.get("totalPages", 0)
        total_elements = first.get("totalElements", 0)
        logger.info("Total convocatorias: %d across %d pages", total_elements, total_pages)

        if progress_callback:
            progress_callback({
                "phase": "full-list",
                "total_pages": total_pages,
                "pages_processed": 0,
                "records_inserted": 0,
            })

        # Insert first page
        items = first.get("content", [])
        if items:
            total_inserted += upsert_convocatorias_list(items)

        pages_processed = 1

        # Fetch remaining pages in batches
        batch_size = 20
        for batch_start in range(1, total_pages, batch_size):
            batch_end = min(batch_start + batch_size, total_pages)
            tasks = [
                fetch_search_page(client, semaphore, p)
                for p in range(batch_start, batch_end)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error("Failed page %d: %s", batch_start + i, result)
                    continue
                items = result.get("content", [])
                if items:
                    total_inserted += upsert_convocatorias_list(items)

            pages_processed = batch_end

            if progress_callback:
                progress_callback({
                    "phase": "full-list",
                    "total_pages": total_pages,
                    "pages_processed": pages_processed,
                    "records_inserted": total_inserted,
                })

            if batch_end % 100 == 0:
                logger.info("Progress: %d/%d pages, %d inserted", batch_end, total_pages, total_inserted)
            await asyncio.sleep(0.1)

    return total_inserted


async def sync_daily(
    progress_callback: ProgressCallback = None,
) -> dict:
    """Incremental daily sync: fetch recent pages + detail + embeddings.

    Args:
        progress_callback: Optional callback receiving progress dicts.

    Returns:
        Dict with counts of operations performed.
    """
    logger.info("Starting daily sync...")
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    new_inserted = 0

    async with httpx.AsyncClient(
        base_url=BDNS_BASE_URL,
        timeout=REQUEST_TIMEOUT,
        headers={"Accept": "application/json"},
    ) as client:
        # Fetch first 10 pages of latest (newest first, should capture daily new ones)
        for page in range(10):
            data = await fetch_search_page(client, semaphore, page)
            items = data.get("content", [])
            if not items:
                break
            inserted = upsert_convocatorias_list(items)
            new_inserted += inserted
            # If no new records on this page, older pages won't have any either
            if inserted == 0:
                break
            await asyncio.sleep(0.1)

    logger.info("Daily list sync: %d new convocatorias", new_inserted)

    if progress_callback:
        progress_callback({"phase": "daily-list", "new_convocatorias": new_inserted})

    # Backfill some details
    detail_count = await sync_backfill_detail(limit=500, progress_callback=progress_callback)

    # Generate some embeddings
    embedding_count = await sync_backfill_embeddings(limit=200, progress_callback=progress_callback)

    return {
        "new_convocatorias": new_inserted,
        "details_fetched": detail_count,
        "embeddings_generated": embedding_count,
    }


async def sync_backfill_detail(
    limit: int = DETAIL_BATCH_SIZE,
    progress_callback: ProgressCallback = None,
) -> int:
    """Fetch detail for convocatorias that don't have it yet.

    Args:
        limit: Max number of details to fetch.
        progress_callback: Optional callback receiving progress dicts.

    Returns:
        Number of details successfully fetched.
    """
    ids = get_unfetched_detail_ids(limit)
    if not ids:
        logger.info("No convocatorias need detail backfill")
        return 0

    logger.info("Backfilling detail for %d convocatorias...", len(ids))
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    fetched = 0

    if progress_callback:
        progress_callback({
            "phase": "backfill-detail",
            "detail_total": len(ids),
            "detail_fetched": 0,
        })

    async with httpx.AsyncClient(
        base_url=BDNS_BASE_URL,
        timeout=REQUEST_TIMEOUT,
        headers={"Accept": "application/json"},
    ) as client:
        # Process in batches of 50
        batch_size = 50
        for batch_start in range(0, len(ids), batch_size):
            batch = ids[batch_start:batch_start + batch_size]
            tasks = [fetch_detail(client, semaphore, numero) for numero in batch]
            results = await asyncio.gather(*tasks)

            for numero, detail in zip(batch, results):
                if detail is not None:
                    update_convocatoria_detail(numero, detail)
                    fetched += 1

            if progress_callback:
                progress_callback({
                    "phase": "backfill-detail",
                    "detail_total": len(ids),
                    "detail_fetched": fetched,
                })

            if batch_start > 0 and batch_start % 500 == 0:
                logger.info("Detail progress: %d/%d", fetched, len(ids))
            await asyncio.sleep(0.1)

    logger.info("Detail backfill complete: %d/%d fetched", fetched, len(ids))

    # Rebuild FTS after adding details
    if fetched > 0:
        rebuild_fts()

    return fetched


async def sync_backfill_embeddings(
    limit: int = EMBEDDING_BATCH_SIZE,
    progress_callback: ProgressCallback = None,
) -> int:
    """Generate embeddings for convocatorias that have detail but no embedding.

    Args:
        limit: Max number of embeddings to generate.
        progress_callback: Optional callback receiving progress dicts.

    Returns:
        Number of embeddings generated.
    """
    from backend.services.convocatorias_db import _get_connection
    from backend.services.embeddings import embedding_to_blob, generate_embeddings_batch

    ids_with_nums = get_unembedded_ids(limit)
    if not ids_with_nums:
        logger.info("No convocatorias need embedding backfill")
        return 0

    logger.info("Generating embeddings for %d convocatorias...", len(ids_with_nums))

    if progress_callback:
        progress_callback({
            "phase": "backfill-embeddings",
            "embedding_total": len(ids_with_nums),
            "embeddings_generated": 0,
        })

    # Load full rows to build embedding texts
    conn = _get_connection()
    try:
        id_list = [str(id_num[0]) for id_num in ids_with_nums]
        placeholders = ",".join("?" * len(id_list))
        rows = conn.execute(
            f"SELECT * FROM convocatorias WHERE id IN ({placeholders})",
            id_list,
        ).fetchall()
    finally:
        conn.close()

    # Build texts
    row_map = {row["id"]: row for row in rows}
    texts_with_ids = []
    for conv_id, _ in ids_with_nums:
        row = row_map.get(conv_id)
        if row:
            text = get_embedding_text(row)
            if text.strip():
                texts_with_ids.append((conv_id, text))

    if not texts_with_ids:
        return 0

    # Generate in API batches
    generated = 0
    for batch_start in range(0, len(texts_with_ids), EMBEDDING_API_BATCH):
        batch = texts_with_ids[batch_start:batch_start + EMBEDDING_API_BATCH]
        batch_ids = [t[0] for t in batch]
        batch_texts = [t[1] for t in batch]

        try:
            embeddings = await generate_embeddings_batch(batch_texts)
            records = [
                (conv_id, embedding_to_blob(emb))
                for conv_id, emb in zip(batch_ids, embeddings)
            ]
            stored = store_embeddings(records)
            generated += stored
            logger.info("Embedding batch: %d/%d generated", generated, len(texts_with_ids))

            if progress_callback:
                progress_callback({
                    "phase": "backfill-embeddings",
                    "embedding_total": len(texts_with_ids),
                    "embeddings_generated": generated,
                })
        except Exception as e:
            logger.error("Embedding batch failed: %s", e)
            break

    logger.info("Embedding backfill complete: %d generated", generated)
    return generated


async def run_sync(
    mode: str = "daily",
    progress_callback: ProgressCallback = None,
) -> dict:
    """Main sync entrypoint.

    Args:
        mode: One of daily, full-list, backfill-detail, backfill-embeddings.
        progress_callback: Optional callback receiving progress dicts.

    Returns:
        Dict with sync results.
    """
    start = time.monotonic()
    init_convocatorias_db()

    if mode == "full-list":
        total = await sync_full_list(progress_callback=progress_callback)
        rebuild_fts()
        result = {"mode": mode, "total_inserted": total}
    elif mode == "backfill-detail":
        count = await sync_backfill_detail(progress_callback=progress_callback)
        result = {"mode": mode, "details_fetched": count}
    elif mode == "backfill-embeddings":
        count = await sync_backfill_embeddings(progress_callback=progress_callback)
        result = {"mode": mode, "embeddings_generated": count}
    else:  # daily
        result = await sync_daily(progress_callback=progress_callback)
        result["mode"] = "daily"

    # Update sync metadata
    conn = sqlite3.connect(CONVOCATORIAS_DB_PATH)
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO conv_sync_metadata (key, value) VALUES ('last_sync', ?)",
            (now,),
        )
        conn.commit()
    finally:
        conn.close()

    elapsed = time.monotonic() - start
    result["elapsed_seconds"] = round(elapsed, 1)
    logger.info("Sync complete: %s in %.1fs", result, elapsed)
    return result


def main() -> None:
    """CLI entrypoint."""
    mode = sys.argv[1] if len(sys.argv) > 1 else "daily"
    valid_modes = {"daily", "full-list", "backfill-detail", "backfill-embeddings"}
    if mode not in valid_modes:
        print(f"Usage: python -m backend.scripts.sync_convocatorias [{' | '.join(valid_modes)}]")
        sys.exit(1)
    asyncio.run(run_sync(mode))


if __name__ == "__main__":
    main()
