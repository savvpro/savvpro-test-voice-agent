"""Unit tests — SessionStore."""

from __future__ import annotations

import time

from app.services.session_store import SessionStore


def test_set_and_get() -> None:
    store = SessionStore(ttl_seconds=60, max_size=10)
    store.set("s1", {"state": "booking"})
    result = store.get("s1")
    assert result == {"state": "booking"}


def test_get_missing_returns_none() -> None:
    store = SessionStore()
    assert store.get("no-such-key") is None


def test_ttl_expiry() -> None:
    store = SessionStore(ttl_seconds=1, max_size=10)
    store.set("s1", {"data": "x"})
    assert store.get("s1") is not None
    time.sleep(1.1)
    assert store.get("s1") is None


def test_max_size_evicts_lru() -> None:
    store = SessionStore(ttl_seconds=60, max_size=3)
    store.set("a", {})
    store.set("b", {})
    store.set("c", {})
    # Access 'a' to make it recently used
    store.get("a")
    # Adding 'd' should evict 'b' (least recently used)
    store.set("d", {})
    assert store.get("b") is None
    assert store.get("a") is not None
    assert store.get("d") is not None


def test_delete() -> None:
    store = SessionStore()
    store.set("s1", {"x": 1})
    store.delete("s1")
    assert store.get("s1") is None


def test_delete_missing_noop() -> None:
    store = SessionStore()
    store.delete("ghost")  # should not raise


def test_len() -> None:
    store = SessionStore(ttl_seconds=60, max_size=100)
    assert len(store) == 0
    store.set("s1", {})
    store.set("s2", {})
    assert len(store) == 2


def test_contains() -> None:
    store = SessionStore()
    store.set("s1", {})
    assert "s1" in store
    assert "s2" not in store
