"""In-memory, idle-expiring server sessions for credentials and analysis state.

``Session`` objects are live server-side objects, not response models.  In particular,
callers must never serialize a session because it contains the user's API key.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .chemistry import AnalysisEngine
from .config import SETTINGS


@dataclass
class Session:
    """Minimal mutable server state; this type must not cross the API boundary."""

    api_key: str = field(repr=False)
    touched_at: float
    engine: AnalysisEngine
    latest_visualization: dict[str, Any] | None = None


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

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(idle_seconds={self._idle_seconds!r}, "
            f"session_count={len(self._sessions)})"
        )

    def create(self, api_key: str) -> str:
        now = self._clock()
        self._prune(now)
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("API key is required")
        token = secrets.token_urlsafe(32)
        while token in self._sessions:  # defensive against an injected RNG failure
            token = secrets.token_urlsafe(32)
        self._sessions[token] = Session(
            api_key=api_key,
            touched_at=now,
            engine=self._engine_factory(),
        )
        return token

    def get(self, token: str) -> Session | None:
        now = self._clock()
        self._prune(now)
        session = self._sessions.get(token)
        if session is not None:
            session.touched_at = now
        return session

    def delete(self, token: str) -> None:
        self._prune(self._clock())
        self._sessions.pop(token, None)

    def _prune(self, now: float) -> None:
        expired = [
            token
            for token, session in self._sessions.items()
            if now - session.touched_at > self._idle_seconds
        ]
        for token in expired:
            self._sessions.pop(token, None)
