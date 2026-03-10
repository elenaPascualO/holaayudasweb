"""OpenAI embeddings service for semantic search."""

import logging
import struct

from backend.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536
BLOB_SIZE = EMBEDDING_DIMS * 4  # float32 = 4 bytes each


def embedding_to_blob(embedding: list[float]) -> bytes:
    """Convert a float list to a compact binary blob.

    Args:
        embedding: List of floats (1536 dimensions).

    Returns:
        Packed bytes (float32 little-endian).
    """
    return struct.pack(f"<{len(embedding)}f", *embedding)


def blob_to_embedding(blob: bytes) -> list[float]:
    """Convert a binary blob back to a float list.

    Args:
        blob: Packed bytes from embedding_to_blob.

    Returns:
        List of floats.
    """
    count = len(blob) // 4
    return list(struct.unpack(f"<{count}f", blob))


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts via OpenAI API.

    Args:
        texts: List of texts to embed (max ~100 per batch for efficiency).

    Returns:
        List of embedding vectors (each 1536 floats).

    Raises:
        ValueError: If OPENAI_API_KEY is not configured.
        Exception: On API errors.
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not configured")

    # Lazy import to avoid requiring openai when not using embeddings
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )

    # Sort by index to maintain order
    sorted_data = sorted(response.data, key=lambda x: x.index)
    return [item.embedding for item in sorted_data]
