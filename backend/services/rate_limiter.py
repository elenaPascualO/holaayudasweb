"""In-memory rate limiter with sliding window, shared across routes."""

import time

from fastapi import HTTPException, Request


class RateLimiter:
    """Simple in-memory sliding window rate limiter.

    Args:
        max_requests: Maximum number of requests allowed per window.
        window_seconds: Time window in seconds.
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, list[float]] = {}

    def check(self, key: str) -> None:
        """Raise HTTP 429 if the key has exceeded the rate limit."""
        now = time.time()
        timestamps = self._hits.get(key, [])
        timestamps = [t for t in timestamps if now - t < self._window]
        if len(timestamps) >= self._max:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Try again later.",
            )
        timestamps.append(now)
        self._hits[key] = timestamps


def get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For behind a reverse proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in the chain is the original client
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Shared rate limiter instances
search_limiter = RateLimiter(max_requests=60, window_seconds=60)
admin_limiter = RateLimiter(max_requests=10, window_seconds=60)
feedback_limiter = RateLimiter(max_requests=5, window_seconds=3600)
