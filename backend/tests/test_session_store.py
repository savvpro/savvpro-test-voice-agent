import pytest

from app.services.session_store import SessionNotFoundError, SessionStore


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_create_and_get():
    store = SessionStore()
    call = store.create(seed=7)
    assert store.get(call.id) is call
    assert call.seed == 7 and call.history == [] and not call.ended


def test_sessions_get_different_ids_and_seeds():
    store = SessionStore()
    a, b = store.create(), store.create()
    assert a.id != b.id
    assert a.seed != b.seed


def test_idle_session_expires():
    clock = FakeClock()
    store = SessionStore(ttl_seconds=60, clock=clock)
    call = store.create()
    clock.t += 61
    with pytest.raises(SessionNotFoundError):
        store.get(call.id)
    assert len(store) == 0


def test_activity_keeps_session_alive():
    clock = FakeClock()
    store = SessionStore(ttl_seconds=60, clock=clock)
    call = store.create()
    for _ in range(3):
        clock.t += 50
        assert store.get(call.id) is call
