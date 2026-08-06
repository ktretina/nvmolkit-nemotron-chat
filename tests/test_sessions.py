from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

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
    assert session.api_key_value() == "key"
    assert session.engine is engine
    assert session.latest_visualization is None
    assert session.provider_status == "unchecked"


def test_reset_replaces_analysis_state_but_preserves_key_and_token() -> None:
    engines = iter([object(), object()])
    store = SessionStore(lambda: next(engines))
    token = store.create("nvapi-secret")
    before = store.get(token)
    assert before is not None
    old_engine = before.engine
    before.latest_visualization = {"kind": "similarity"}
    before.provider_status = "available"

    assert store.reset(token) is True

    after = store.get(token)
    assert after is before
    assert after.api_key_value() == "nvapi-secret"
    assert after.engine is not old_engine
    assert after.latest_visualization is None
    assert after.provider_status == "unchecked"


def test_reset_missing_or_expired_session_is_false() -> None:
    clock = Clock()
    store = SessionStore(lambda: object(), clock=clock, idle_seconds=10)
    token = store.create("key")
    clock.now += 11

    assert store.reset(token) is False
    assert store.reset("missing") is False


def test_reset_waits_for_an_active_session_lease() -> None:
    store = SessionStore(lambda: object())
    token = store.create("key")
    reset_started = threading.Event()

    def reset() -> bool:
        reset_started.set()
        return store.reset(token)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with store.lease(token) as session:
            assert session is not None
            future = pool.submit(reset)
            assert reset_started.wait(timeout=1)
            assert not future.done()
        assert future.result(timeout=1) is True


def test_session_serializers_never_expose_raw_key() -> None:
    raw_key = "nvapi-secret"
    store = SessionStore(lambda: object())
    session = store.get(store.create(raw_key))

    assert session is not None
    probes = (
        repr(session),
        repr(asdict(session)),
        json.dumps(asdict(session), default=str),
    )
    assert all(raw_key not in probe for probe in probes)


def test_concurrent_store_operations_do_not_corrupt_session_map() -> None:
    store = SessionStore(lambda: object())

    def exercise(index: int) -> None:
        for iteration in range(100):
            token = store.create(f"key-{index}-{iteration}")
            assert store.get(token) is not None
            if iteration % 2:
                store.delete(token)

    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(exercise, range(24)))


def test_same_session_leases_serialize_mutation() -> None:
    store = SessionStore(lambda: object())
    token = store.create("key")
    active = 0
    maximum_active = 0
    counter_lock = threading.Lock()

    def mutate() -> None:
        nonlocal active, maximum_active
        with store.lease(token) as session:
            assert session is not None
            with counter_lock:
                active += 1
                maximum_active = max(maximum_active, active)
            threading.Event().wait(0.01)
            with counter_lock:
                active -= 1

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: mutate(), range(16)))

    assert maximum_active == 1


def test_different_session_leases_overlap() -> None:
    store = SessionStore(lambda: object())
    tokens = [store.create("one"), store.create("two")]
    rendezvous = threading.Barrier(2)

    def lease(token: str) -> None:
        with store.lease(token) as session:
            assert session is not None
            rendezvous.wait(timeout=1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lease, tokens))


def test_global_store_lock_is_free_during_lease_body() -> None:
    store = SessionStore(lambda: object())
    token = store.create("one")
    lease_started = threading.Event()
    release_lease = threading.Event()

    def hold_lease() -> None:
        with store.lease(token) as session:
            assert session is not None
            lease_started.set()
            assert release_lease.wait(timeout=1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(hold_lease)
        assert lease_started.wait(timeout=1)
        other = pool.submit(store.create, "two")
        assert other.result(timeout=0.5)
        release_lease.set()
        future.result(timeout=1)
