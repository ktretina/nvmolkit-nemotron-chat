from __future__ import annotations

import json
import threading
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, TypeAlias, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import ChatRequest, create_app

if TYPE_CHECKING:
    AnalysisEngine: TypeAlias = Any
    AnalysisKind: TypeAlias = Any
    AnalysisParameters: TypeAlias = Any
    AnalysisResult: TypeAlias = Any
    SessionStore: TypeAlias = Any
    NemotronError: Any
else:
    from app.chemistry import AnalysisEngine
    from app.models import AnalysisKind, AnalysisParameters, AnalysisResult
    from app.nemotron import NemotronError
    from app.sessions import SessionStore


ALLOWED_PROMPTS = {"fingerprints", "similarity", "clusters", "conformers"}
SECRET = "nvapi-secret-that-must-never-leak"


def _artifact(
    kind: AnalysisKind, sentinel: str = "artifact-secret-sentinel"
) -> dict[str, Any]:
    if kind is AnalysisKind.FINGERPRINT_DENSITY:
        return {
            "molecule_ids": ["M1", "M2"],
            "active_bit_counts": [3, 5],
            "sentinel": sentinel,
        }
    if kind is AnalysisKind.SIMILARITY:
        return {
            "molecule_ids": ["M1", "M2"],
            "matrix": [[1.0, 0.4], [0.4, 1.0]],
            "sentinel": sentinel,
        }
    if kind is AnalysisKind.CLUSTERS:
        return {
            "cluster_sizes": [2, 1],
            "representative_molecule_ids": ["M1", "M2"],
            "sentinel": sentinel,
        }
    return {
        "per_conformer_records": [
            {
                "molecule_id": "M1",
                "conformer_id": "M1:0",
                "conformer_index": 0,
                "relative_energy_kcal_mol": 0.0,
            }
        ],
        "renderable_structures": [
            {
                "molecule_id": "M1",
                "conformer_id": "M1:0",
                "conformer_index": 0,
                "relative_energy_kcal_mol": 0.0,
                "atoms": [{"index": 0, "element": "C"}],
                "bonds": [],
                "coordinates": [[0.0, 0.0, 0.0]],
            }
        ],
        "sentinel": sentinel,
    }


class FakeEngine(AnalysisEngine):
    def __init__(
        self, *, fail: Exception | None = None, gate: threading.Barrier | None = None
    ) -> None:
        self.fail = fail
        self.gate = gate
        self.calls: list[tuple[AnalysisKind, AnalysisParameters]] = []

    def run(
        self,
        kind: AnalysisKind | str,
        params: Mapping[str, Any] | AnalysisParameters | None,
    ) -> AnalysisResult:
        analysis_kind = AnalysisKind(kind)
        analysis_params = (
            AnalysisParameters.model_validate(params or {})
            if params is None or isinstance(params, Mapping)
            else params
        )
        self.calls.append((analysis_kind, analysis_params))
        if self.gate is not None:
            self.gate.wait(timeout=2)
        if self.fail is not None:
            raise self.fail
        return AnalysisResult(
            kind=analysis_kind,
            summary={"kind": analysis_kind.value},
            artifact=_artifact(analysis_kind),
        )


def _completion(*, tool: str | None = None, content: str | None = None) -> object:
    calls = []
    if tool is not None:
        calls = [
            SimpleNamespace(
                id="call-1",
                type="function",
                function=SimpleNamespace(name=tool, arguments="{}"),
            )
        ]
    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(tool_calls=calls, content=content))
        ]
    )


class FakeCompletions:
    def __init__(self, responses: list[object | Exception]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> object:
        self.requests.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class ClientFactory:
    def __init__(self, responses: list[object | Exception]) -> None:
        self.completions = FakeCompletions(responses)
        self.keys: list[str] = []

    def __call__(self, key: str) -> object:
        self.keys.append(key)
        return SimpleNamespace(chat=SimpleNamespace(completions=self.completions))


class Clock:
    def __init__(self) -> None:
        self.now = 10.0

    def __call__(self) -> float:
        return self.now


def _client(
    engines: Sequence[FakeEngine],
    responses: list[object | Exception],
    *,
    store: SessionStore | None = None,
    readiness: Any = None,
) -> tuple[TestClient, ClientFactory, SessionStore]:
    iterator = iter(engines)
    current_store = store or SessionStore(lambda: next(iterator))
    factory = ClientFactory(responses)
    app = create_app(
        session_store=current_store,
        nemotron_client_factory=factory,
        readiness=readiness
        or (lambda: {"cuda": True, "pytorch": True, "nvmolkit": True}),
        frontend_dist=None,
    )
    return TestClient(app, base_url="https://testserver"), factory, current_store


def _authenticate(client: TestClient, key: str = SECRET) -> None:
    response = client.post("/api/session/key", json={"api_key": key})
    assert response.status_code == 200


def test_suggested_similarity_bypasses_selection_and_runs_exact_kind() -> None:
    engine = FakeEngine()
    client, factory, _ = _client(
        [engine], [_completion(content="Similarity is moderate.")]
    )
    _authenticate(client)

    response = client.post("/api/chat", json={"prompt_id": "similarity"})

    assert response.status_code == 200
    assert response.json()["visualization"]["kind"] == "similarity"
    assert [call[0] for call in engine.calls] == [AnalysisKind.SIMILARITY]
    assert len(factory.completions.requests) == 1
    assert "tools" not in factory.completions.requests[0]


def test_freeform_selects_once_then_runs_selected_kind() -> None:
    engine = FakeEngine()
    factory_responses = [
        _completion(tool="analyze_cluster_distribution"),
        _completion(content="Two clusters are present."),
    ]
    client, factory, _ = _client([engine], factory_responses)
    _authenticate(client)

    response = client.post("/api/chat", json={"message": "  show molecular groups  "})

    assert response.status_code == 200
    assert engine.calls[0][0] is AnalysisKind.CLUSTERS
    assert len(factory.completions.requests) == 2
    assert factory.completions.requests[0]["tool_choice"] == "required"


@pytest.mark.parametrize("failure_stage", ["runtime", "selection", "visualization"])
def test_failures_preserve_previous_visualization(failure_stage: str) -> None:
    engine = FakeEngine()
    responses: list[object | Exception] = [_completion(content="Initial.")]
    client, factory, store = _client([engine], responses)
    _authenticate(client)
    assert client.post("/api/chat", json={"prompt_id": "similarity"}).status_code == 200
    previous = client.get("/api/session").json()["visualization"]
    if failure_stage == "runtime":
        engine.fail = RuntimeError("CUDA secret failure")
        request = {"prompt_id": "clusters"}
    elif failure_stage == "selection":
        factory.completions.responses.append(RuntimeError("raw tool json and secret"))
        request = {"message": "choose something"}
    else:
        original = engine.run

        def invalid(
            kind: AnalysisKind | str,
            params: Mapping[str, Any] | AnalysisParameters | None,
        ) -> AnalysisResult:
            result = original(kind, params)
            result.artifact = {"matrix": [[float("nan")]], "molecule_ids": ["M1"]}
            return result

        engine.run = invalid  # type: ignore[method-assign]
        request = {"prompt_id": "similarity"}
    failed = client.post("/api/chat", json=request)
    assert failed.status_code in {422, 503}
    assert client.get("/api/session").json()["visualization"] == previous
    assert SECRET not in failed.text
    assert store.get(client.cookies["session"]) is not None


def test_interpretation_failure_keeps_new_visualization_and_marks_unavailable() -> None:
    engine = FakeEngine()
    client, _, _ = _client([engine], [RuntimeError("hosted key leak")])
    _authenticate(client)

    response = client.post("/api/chat", json={"prompt_id": "fingerprints"})

    assert response.status_code == 200
    visual = response.json()["visualization"]
    assert visual["kind"] == "fingerprint_density"
    assert visual["interpretation"] is None
    assert visual["interpretation_unavailable"] is True
    assert client.get("/api/session").json()["visualization"] == visual


def test_session_cookie_security_secrecy_get_delete_and_expiry() -> None:
    clock = Clock()
    engine = FakeEngine()
    store = SessionStore(lambda: engine, clock=clock, idle_seconds=10)
    client, factory, _ = _client([], [], store=store)

    created = client.post("/api/session/key", json={"api_key": SECRET})

    assert created.json() == {"authenticated": True}
    assert SECRET not in created.text and SECRET not in repr(created.json())
    cookie = created.headers["set-cookie"].lower()
    assert all(
        flag in cookie
        for flag in ("httponly", "secure", "samesite=strict", "path=/", "max-age=3600")
    )
    assert client.get("/api/session").json() == {
        "authenticated": True,
        "visualization": None,
    }
    token = client.cookies["session"]
    assert SECRET not in repr(store) and SECRET not in repr(store.get(token))
    clock.now += 11
    assert client.get("/api/session").json() == {
        "authenticated": False,
        "visualization": None,
    }
    deleted = client.delete("/api/session")
    assert deleted.json() == {"authenticated": False}
    cleared = deleted.headers["set-cookie"].lower()
    assert all(
        flag in cleared for flag in ("httponly", "secure", "samesite=strict", "path=/")
    )
    assert factory.keys == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"prompt_id": "similarity", "message": "also"},
        {"extra": 1},
        {"message": "   "},
        {"message": "x" * 2001},
        {"prompt_id": "invalid"},
    ],
)
def test_chat_request_is_strict_and_exactly_one(payload: dict[str, Any]) -> None:
    with pytest.raises(Exception):
        ChatRequest.model_validate(payload)


def test_chat_message_is_trimmed() -> None:
    assert ChatRequest.model_validate({"message": "  hello  "}).message == "hello"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"prompt_id": "similarity", "message": "also"},
        {"extra": 1},
        {"message": "   "},
        {"message": "x" * 2001},
        {"prompt_id": "invalid"},
    ],
)
def test_malformed_chat_body_returns_safe_capability_payload(
    payload: dict[str, Any],
) -> None:
    client, _, _ = _client([FakeEngine()], [])
    _authenticate(client)

    response = client.post("/api/chat", json=payload)

    assert response.status_code == 422
    assert set(response.json()["detail"]["allowed_prompt_ids"]) == ALLOWED_PROMPTS
    assert SECRET not in response.text


def test_missing_and_expired_session_are_401() -> None:
    clock = Clock()
    store = SessionStore(lambda: FakeEngine(), clock=clock, idle_seconds=10)
    client, _, _ = _client([], [], store=store)
    assert client.post("/api/chat", json={"prompt_id": "similarity"}).status_code == 401
    _authenticate(client)
    clock.now += 11
    assert client.post("/api/chat", json={"prompt_id": "similarity"}).status_code == 401


def test_unsupported_selection_is_safe_and_lists_capabilities() -> None:
    engine = FakeEngine()
    client, _, _ = _client([engine], [_completion(tool="unsupported_raw_tool")])
    _authenticate(client)

    response = client.post("/api/chat", json={"message": "do arbitrary raw work"})

    assert response.status_code == 422
    payload = response.json()
    assert set(payload["detail"]["allowed_prompt_ids"]) == ALLOWED_PROMPTS
    assert "supported" in payload["detail"]["message"].lower()
    serialized = json.dumps(payload)
    assert "unsupported_raw_tool" not in serialized
    assert SECRET not in serialized


def test_client_factory_failure_is_safe_and_does_not_expose_key() -> None:
    store = SessionStore(lambda: FakeEngine())

    def failed_factory(_key: str) -> object:
        raise RuntimeError(f"client setup rejected {SECRET}")

    app = create_app(
        session_store=store,
        nemotron_client_factory=failed_factory,
        readiness=lambda: True,
        frontend_dist=None,
    )
    client = TestClient(app, base_url="https://testserver")
    _authenticate(client)

    response = client.post("/api/chat", json={"message": "show similarity"})

    assert response.status_code == 422
    assert SECRET not in response.text


def test_health_is_cached_injected_and_secret_safe() -> None:
    calls = 0

    def ready() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"cuda": True, "pytorch": True, "nvmolkit": True, "detail": SECRET}

    client, _, _ = _client([], [], readiness=ready)
    first = client.get("/api/health")
    second = client.get("/api/health")
    assert first.status_code == second.status_code == 200
    assert calls == 1
    assert first.json() == {
        "process": {"ready": True},
        "dependencies": {
            "ready": True,
            "checks": {"cuda": True, "pytorch": True, "nvmolkit": True},
        },
        "ready": True,
    }
    assert SECRET not in first.text

    unready, _, _ = _client(
        [],
        [],
        readiness=lambda: {
            "cuda": False,
            "pytorch": True,
            "nvmolkit": True,
            "error": SECRET,
        },
    )
    response = unready.get("/api/health")
    assert response.status_code == 503
    assert response.json()["ready"] is False
    assert response.json()["process"] == {"ready": True}
    assert response.json()["dependencies"]["ready"] is False
    assert SECRET not in response.text


def test_interpreter_receives_textual_metadata_only_not_artifact() -> None:
    engine = FakeEngine()
    client, factory, _ = _client([engine], [_completion(content="Text.")])
    _authenticate(client)
    assert client.post("/api/chat", json={"prompt_id": "similarity"}).status_code == 200

    payload = json.dumps(factory.completions.requests[0])
    assert "artifact-secret-sentinel" not in payload
    assert '"matrix"' not in payload and "coordinates" not in payload
    assert "Pairwise molecular similarity" in payload
    assert "Tanimoto similarity" in payload


def test_same_session_chats_serialize_and_different_sessions_overlap() -> None:
    active = 0
    maximum = 0
    lock = threading.Lock()

    class TrackingEngine(FakeEngine):
        def run(
            self,
            kind: AnalysisKind | str,
            params: Mapping[str, Any] | AnalysisParameters | None,
        ) -> AnalysisResult:
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            threading.Event().wait(0.04)
            try:
                return super().run(kind, params)
            finally:
                with lock:
                    active -= 1

    engines = [TrackingEngine(), TrackingEngine()]
    client, _, _ = _client(engines, [NemotronError("offline")] * 4)
    _authenticate(client, "one")
    token_one = client.cookies["session"]
    _authenticate(client, "two")
    token_two = client.cookies["session"]

    def post(token: str) -> int:
        worker = TestClient(
            client.app, base_url="https://testserver", cookies={"session": token}
        )
        return worker.post("/api/chat", json={"prompt_id": "similarity"}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(post, [token_one, token_one])) == [200, 200]
    assert maximum == 1
    maximum = 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(post, [token_one, token_two])) == [200, 200]
    assert maximum == 2


def test_key_validation_is_bounded_without_client_calls() -> None:
    client, factory, _ = _client([FakeEngine()], [])
    for key in ("", "   ", "x" * 513):
        response = client.post("/api/session/key", json={"api_key": key})
        assert response.status_code == 422
        if key:
            assert key not in response.text
    assert factory.keys == []


def test_app_exposes_only_required_api_routes() -> None:
    client, _, _ = _client([], [])

    paths = {cast(Any, route).path for route in cast(FastAPI, client.app).routes}
    assert {path for path in paths if path.startswith("/api/")} == {
        "/api/session/key",
        "/api/session",
        "/api/chat",
        "/api/health",
    }
    assert paths.isdisjoint(
        {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
    )
