from __future__ import annotations

import pytest

from app.sessions import SessionStore


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_create_returns_unique_opaque_tokens_and_hides_key() -> None:
    clock = Clock()
    store = SessionStore(lambda: object(), clock=clock)

    first = store.create("nvapi-secret")
    second = store.create("another-secret")

    assert first != second
    assert len(first) >= 43
    assert all(character.isalnum() or character in "-_" for character in first)
    assert "nvapi-secret" not in repr(store)
    assert "another-secret" not in repr(store)
    assert first not in repr(store)
    assert "nvapi-secret" not in repr(store.get(first))


@pytest.mark.parametrize("api_key", ["", " ", "\t\n"])
def test_create_rejects_blank_keys(api_key: str) -> None:
    store = SessionStore(lambda: object())

    with pytest.raises(ValueError, match="API key is required"):
        store.create(api_key)


def test_get_refreshes_idle_timeout_and_exact_boundary_is_valid() -> None:
    clock = Clock()
    store = SessionStore(lambda: object(), clock=clock, idle_seconds=3600)
    token = store.create("key")

    clock.now += 3600
    session = store.get(token)
    assert session is not None
    assert session.touched_at == 3700

    clock.now += 3600
    assert store.get(token) is session


def test_session_expires_after_idle_timeout() -> None:
    clock = Clock()
    store = SessionStore(lambda: object(), clock=clock, idle_seconds=3600)
    token = store.create("key")

    clock.now += 3601

    assert store.get(token) is None


def test_delete_removes_session() -> None:
    store = SessionStore(lambda: object())
    token = store.create("key")

    store.delete(token)

    assert store.get(token) is None


def test_every_public_operation_prunes_all_expired_sessions() -> None:
    clock = Clock()
    store = SessionStore(lambda: object(), clock=clock, idle_seconds=10)
    first = store.create("one")
    second = store.create("two")
    clock.now += 11

    third = store.create("three")

    assert store.get(first) is None
    assert store.get(second) is None
    assert store.get(third) is not None


def test_session_contains_only_live_server_state() -> None:
    engine = object()
    store = SessionStore(lambda: engine)
    token = store.create("key")

    session = store.get(token)

    assert session is not None
    assert session.api_key == "key"
    assert session.engine is engine
    assert session.latest_visualization is None
