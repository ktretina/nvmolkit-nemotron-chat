"""In-memory, idle-expiring server sessions for credentials and analysis state.

``Session`` objects are live server-side objects, not response models.  In particular,
callers must never serialize a session because it contains the user's API key.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, ClassVar, Iterator

from pydantic import SecretStr

from .chemistry import AnalysisEngine
from .config import SETTINGS


@dataclass
class Session:
    """Minimal mutable server state; this type must not cross the API boundary."""

    api_key: SecretStr = field(repr=False)
    touched_at: float
    engine: AnalysisEngine
    latest_visualization: dict[str, Any] | None = None
    _lock: ClassVar[threading.RLock]
    _active_leases: ClassVar[int]

    def __post_init__(self) -> None:
        # Internal synchronization state is intentionally not a dataclass field, so
        # serializers such as dataclasses.asdict cannot traverse the lock.
        self._lock = threading.RLock()
        self._active_leases = 0

    def api_key_value(self) -> str:
        """Return the raw key for local client construction only."""

        return self.api_key.get_secret_value()


class SessionStore:
    """Process-local session storage with access-based idle expiry."""

    def __init__(
        self,
        engine_factory: Callable[[], AnalysisEngine],
        *,
        clock: Callable[[], float] = time.monotonic,
        idle_seconds: float = SETTINGS.session_idle_seconds,
    ) -> None:
        if idle_seconds <= 0:
            raise ValueError("idle timeout must be positive")
        self._engine_factory = engine_factory
        self._clock = clock
        self._idle_seconds = idle_seconds
        self._sessions: dict[str, Session] = {}
        self._lock = threading.RLock()

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"{type(self).__name__}(idle_seconds={self._idle_seconds!r}, "
                f"session_count={len(self._sessions)})"
            )

    def create(self, api_key: str) -> str:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("API key is required")
        with self._lock:
            self._prune(self._clock())
        engine = self._engine_factory()
        token = secrets.token_urlsafe(32)
        with self._lock:
            now = self._clock()
            self._prune(now)
            while token in self._sessions:  # defensive against an RNG failure
                token = secrets.token_urlsafe(32)
            self._sessions[token] = Session(
                api_key=SecretStr(api_key),
                touched_at=now,
                engine=engine,
            )
        return token

    def get(self, token: str) -> Session | None:
        with self._lock:
            now = self._clock()
            self._prune(now)
            session = self._sessions.get(token)
            if session is not None:
                session.touched_at = now
            return session

    def delete(self, token: str) -> None:
        with self._lock:
            self._prune(self._clock())
            session = self._sessions.get(token)
        if session is None:
            return
        with session._lock:
            with self._lock:
                self._prune(self._clock())
                if self._sessions.get(token) is session:
                    self._sessions.pop(token, None)

    @contextmanager
    def lease(self, token: str) -> Iterator[Session | None]:
        """Serialize mutation of one live session without blocking other sessions."""

        with self._lock:
            self._prune(self._clock())
            session = self._sessions.get(token)
        if session is None:
            yield None
            return

        session._lock.acquire()
        active = False
        try:
            with self._lock:
                now = self._clock()
                self._prune(now)
                if self._sessions.get(token) is session:
                    session.touched_at = now
                    session._active_leases += 1
                    active = True
            if not active:
                yield None
                return
            yield session
        finally:
            if active:
                with self._lock:
                    session._active_leases -= 1
                    if self._sessions.get(token) is session:
                        session.touched_at = self._clock()
            session._lock.release()

    def _prune(self, now: float) -> None:
        expired = [
            token
            for token, session in self._sessions.items()
            if session._active_leases == 0
            and now - session.touched_at > self._idle_seconds
        ]
        for token in expired:
            self._sessions.pop(token, None)
