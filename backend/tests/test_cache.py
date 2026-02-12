"""Tests for the TTL cache."""

import time

from backend.services.cache import TTLCache


def test_set_and_get():
    """Setting a value and getting it back works."""
    c = TTLCache()
    c.set("key1", {"data": "value"}, ttl=60)
    assert c.get("key1") == {"data": "value"}


def test_get_missing_key_returns_none():
    """Getting a non-existent key returns None."""
    c = TTLCache()
    assert c.get("nonexistent") is None


def test_expired_entry_returns_none():
    """An expired entry returns None and is removed."""
    c = TTLCache()
    c.set("key1", "value", ttl=0)  # Expires immediately
    time.sleep(0.01)
    assert c.get("key1") is None
    assert c.size == 0


def test_max_size_eviction():
    """When max size is reached, oldest entry is evicted."""
    c = TTLCache(max_size=3)
    c.set("a", 1, ttl=60)
    c.set("b", 2, ttl=60)
    c.set("c", 3, ttl=60)
    c.set("d", 4, ttl=60)  # Should evict "a" (oldest expiry)
    assert c.get("a") is None
    assert c.get("d") == 4
    assert c.size == 3


def test_evict_expired():
    """Expired entries are cleaned up when eviction runs."""
    c = TTLCache()
    c.set("alive", "yes", ttl=60)
    c.set("dead", "no", ttl=0)
    time.sleep(0.01)
    c._evict_expired()
    assert c.get("alive") == "yes"
    assert c.get("dead") is None
    assert c.size == 1


def test_clear():
    """Clear removes all entries."""
    c = TTLCache()
    c.set("a", 1, ttl=60)
    c.set("b", 2, ttl=60)
    c.clear()
    assert c.size == 0
    assert c.get("a") is None


def test_overwrite_existing_key():
    """Setting an existing key overwrites the value and TTL."""
    c = TTLCache()
    c.set("key", "old", ttl=60)
    c.set("key", "new", ttl=120)
    assert c.get("key") == "new"
